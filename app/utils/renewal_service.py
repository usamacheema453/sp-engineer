# app/services/renewal_service.py - Automatic renewal cron job

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.user import User
from app.models.subscription import UserSubscription, PaymentHistory, BillingCycle
from app.utils.stripe_service import charge_saved_payment_method
from app.utils.email import send_email
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RenewalService:
    def __init__(self):
        self.db = SessionLocal()
        self.max_retry_attempts = 3
        self.retry_delay_days = 2
    
    def __del__(self):
        self.db.close()
    
    def run_renewal_check(self):
        """Main method to check and process renewals"""
        logger.info("🔄 Starting renewal check...")
        
        try:
            # Get subscriptions that need renewal
            subscriptions_to_renew = self.get_subscriptions_for_renewal()
            logger.info(f"Found {len(subscriptions_to_renew)} subscriptions to process")
            
            success_count = 0
            failure_count = 0
            
            for subscription in subscriptions_to_renew:
                try:
                    result = self.process_renewal(subscription)
                    if result:
                        success_count += 1
                        logger.info(f"✅ Renewal successful for user {subscription.user.email}")
                    else:
                        failure_count += 1
                        logger.warning(f"❌ Renewal failed for user {subscription.user.email}")
                except Exception as e:
                    failure_count += 1
                    logger.error(f"❌ Error processing renewal for user {subscription.user.email}: {e}")
            
            # Send summary report
            self.send_renewal_summary(success_count, failure_count)
            
            logger.info(f"🏁 Renewal check completed. Success: {success_count}, Failures: {failure_count}")
            
        except Exception as e:
            logger.error(f"❌ Critical error in renewal check: {e}")
        finally:
            self.db.close()
    
    def get_subscriptions_for_renewal(self):
        """Get subscriptions that need renewal"""
        # Get subscriptions expiring in the next 3 days
        renewal_threshold = datetime.utcnow() + timedelta(days=3)
        
        subscriptions = self.db.query(UserSubscription).join(User).filter(
            UserSubscription.active == True,
            UserSubscription.auto_renew == True,
            UserSubscription.renewal_failed == False,
            UserSubscription.next_renewal_date <= renewal_threshold,
            UserSubscription.payment_method_id.isnot(None),  # Must have saved payment method
            User.auto_renew_enabled == True  # User hasn't globally disabled auto-renewal
        ).all()
        
        # Also get failed renewals that are ready for retry
        retry_subscriptions = self.db.query(UserSubscription).join(User).filter(
            UserSubscription.active == True,
            UserSubscription.auto_renew == True,
            UserSubscription.renewal_failed == True,
            UserSubscription.renewal_attempts < self.max_retry_attempts,
            UserSubscription.last_renewal_attempt <= datetime.utcnow() - timedelta(days=self.retry_delay_days),
            UserSubscription.payment_method_id.isnot(None),
            User.auto_renew_enabled == True
        ).all()
        
        return list(set(subscriptions + retry_subscriptions))
    
    def process_renewal(self, subscription: UserSubscription) -> bool:
        """Process renewal for a single subscription"""
        user = subscription.user
        plan = subscription.plan
        
        logger.info(f"🔄 Processing renewal for {user.email} - {plan.name} ({subscription.billing_cycle.value})")
        
        # Calculate renewal amount
        if subscription.billing_cycle == BillingCycle.yearly:
            amount = plan.yearly_price
            renewal_period_days = 365
        else:
            amount = plan.monthly_price
            renewal_period_days = 30
        
        if not amount:
            logger.error(f"❌ No price configured for {plan.name} - {subscription.billing_cycle.value}")
            return False
        
        # Update renewal attempt tracking
        subscription.renewal_attempts += 1
        subscription.last_renewal_attempt = datetime.utcnow()
        
        try:
            # Attempt to charge the saved payment method
            payment_result = charge_saved_payment_method(
                customer_id=user.stripe_customer_id,
                payment_method_id=subscription.payment_method_id,
                amount=amount,
                metadata={
                    'type': 'renewal',
                    'user_id': str(user.id),
                    'subscription_id': str(subscription.id),
                    'plan_name': plan.name,
                    'billing_cycle': subscription.billing_cycle.value
                }
            )
            
            if payment_result.get('status') == 'succeeded':
                # Payment successful - extend subscription
                self.extend_subscription(subscription, renewal_period_days, payment_result)
                
                # Create payment history record
                self.create_payment_record(subscription, payment_result, amount, True)
                
                # Send success notification
                self.send_renewal_success_email(user, plan, subscription.billing_cycle.value, amount)
                
                # Reset failure tracking
                subscription.renewal_failed = False
                subscription.failure_reason = None
                subscription.renewal_attempts = 0
                
                self.db.commit()
                return True
            
            else:
                # Payment failed
                error_message = payment_result.get('message', 'Payment failed')
                self.handle_renewal_failure(subscription, error_message, payment_result.get('error'))
                self.db.commit()
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception during renewal for {user.email}: {e}")
            self.handle_renewal_failure(subscription, str(e), 'exception')
            self.db.commit()
            return False
    
    def extend_subscription(self, subscription: UserSubscription, days: int, payment_result: dict):
        """Extend subscription period"""
        new_expiry = subscription.expiry_date + timedelta(days=days)
        subscription.expiry_date = new_expiry
        subscription.next_renewal_date = new_expiry
        subscription.last_payment_date = datetime.utcnow()
        subscription.last_payment_intent_id = payment_result.get('payment_intent_id')
        
        # Reset usage counters for new period
        subscription.queries_used = 0
        subscription.documents_uploaded = 0
    
    def create_payment_record(self, subscription: UserSubscription, payment_result: dict, amount: int, is_renewal: bool):
        """Create payment history record"""
        payment_record = PaymentHistory(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            payment_intent_id=payment_result.get('payment_intent_id'),
            amount=amount,
            status=payment_result.get('status'),
            billing_cycle=subscription.billing_cycle,
            is_renewal=is_renewal,
            metadata=str(payment_result.get('metadata', {}))
        )
        self.db.add(payment_record)
    
    def handle_renewal_failure(self, subscription: UserSubscription, error_message: str, error_type: str):
        """Handle renewal failure"""
        subscription.renewal_failed = True
        subscription.failure_reason = error_message
        
        user = subscription.user
        plan = subscription.plan
        
        # Check if we've reached max retry attempts
        if subscription.renewal_attempts >= self.max_retry_attempts:
            logger.warning(f"⚠️ Max retry attempts reached for {user.email}. Disabling auto-renewal.")
            subscription.auto_renew = False
            self.send_renewal_failed_final_email(user, plan, error_message)
        else:
            # Send retry notification
            next_retry = datetime.utcnow() + timedelta(days=self.retry_delay_days)
            self.send_renewal_failed_retry_email(user, plan, error_message, next_retry)
    
    def send_renewal_success_email(self, user: User, plan, billing_cycle: str, amount: int):
        """Send renewal success notification"""
        if not user.email_notifications:
            return
        
        subject = f"Payment Successful - {plan.name} Plan Renewed"
        body = f"""
Hi {user.full_name},

Your {plan.name} plan has been successfully renewed!

Plan: {plan.name}
Billing Cycle: {billing_cycle.title()}
Amount: ${amount / 100:.2f}
Next Renewal: {datetime.utcnow() + timedelta(days=365 if billing_cycle == 'yearly' else 30)}

Thank you for continuing to use SuperEngineer!

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Renewal success email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send renewal success email to {user.email}: {e}")
    
    def send_renewal_failed_retry_email(self, user: User, plan, error_message: str, next_retry: datetime):
        """Send renewal failure notification with retry info"""
        if not user.email_notifications:
            return
        
        subject = f"Payment Failed - {plan.name} Plan Renewal"
        body = f"""
Hi {user.full_name},

We encountered an issue renewing your {plan.name} plan:

Error: {error_message}

Don't worry! We'll automatically retry the payment on {next_retry.strftime('%B %d, %Y')}.

If you'd like to update your payment method, please log in to your account.

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Renewal retry email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send renewal retry email to {user.email}: {e}")
    
    def send_renewal_failed_final_email(self, user: User, plan, error_message: str):
        """Send final renewal failure notification"""
        if not user.email_notifications:
            return
        
        subject = f"Action Required - {plan.name} Plan Renewal Failed"
        body = f"""
Hi {user.full_name},

We were unable to renew your {plan.name} plan after multiple attempts:

Final Error: {error_message}

Your subscription will expire soon. To continue using SuperEngineer:
1. Log in to your account
2. Update your payment method
3. Manually renew your subscription

We've temporarily disabled auto-renewal for your account.

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Final renewal failure email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send final renewal failure email to {user.email}: {e}")
    
    def send_renewal_summary(self, success_count: int, failure_count: int):
        """Send renewal summary to admin"""
        if success_count == 0 and failure_count == 0:
            return
        
        subject = f"Renewal Summary - {datetime.utcnow().strftime('%Y-%m-%d')}"
        body = f"""
Renewal Process Summary:

✅ Successful Renewals: {success_count}
❌ Failed Renewals: {failure_count}
📅 Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

Total Processed: {success_count + failure_count}
        """
        
        # Send to admin email (configure in environment)
        admin_email = "admin@superengineer.com"  # Replace with actual admin email
        try:
            send_email(admin_email, subject, body)
        except Exception as e:
            logger.error(f"❌ Failed to send renewal summary: {e}")

# ✅ Standalone script to run the renewal service
def run_renewal_service():
    """Entry point for cron job"""
    service = RenewalService()
    service.run_renewal_check()

if __name__ == "__main__":
    run_renewal_service()