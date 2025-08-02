# app/services/renewal_service_enhanced.py - Enhanced Renewal with Saved Payment Methods

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.user import User
from app.models.subscription import UserSubscription, PaymentHistory, BillingCycle
from app.utils.email import send_email
import stripe
import logging
from app.config import STRIPE_SECRET_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

class EnhancedRenewalService:
    def __init__(self):
        self.db = SessionLocal()
        self.max_retry_attempts = 3
        self.retry_delay_days = 2
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def run_renewal_check(self):
        """Main method to check and process renewals using saved payment methods"""
        logger.info("🔄 Starting enhanced renewal check...")
        
        try:
            # Get subscriptions that need renewal
            subscriptions_to_renew = self.get_subscriptions_for_renewal()
            logger.info(f"Found {len(subscriptions_to_renew)} subscriptions to process")
            
            success_count = 0
            failure_count = 0
            
            for subscription in subscriptions_to_renew:
                try:
                    result = self.process_subscription_renewal(subscription)
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
            
            logger.info(f"🏁 Enhanced renewal check completed. Success: {success_count}, Failures: {failure_count}")
            
        except Exception as e:
            logger.error(f"❌ Critical error in renewal check: {e}")
        finally:
            self.db.close()
    
    def get_subscriptions_for_renewal(self):
        """Get subscriptions that need renewal and have saved payment methods"""
        # Get subscriptions expiring in the next 3 days
        renewal_threshold = datetime.utcnow() + timedelta(days=3)
        
        subscriptions = self.db.query(UserSubscription).join(User).filter(
            UserSubscription.active == True,
            UserSubscription.auto_renew == True,
            UserSubscription.renewal_failed == False,
            UserSubscription.next_renewal_date <= renewal_threshold,
            UserSubscription.payment_method_id.isnot(None),  # ✅ Must have saved payment method
            User.auto_renew_enabled == True,
            User.stripe_customer_id.isnot(None)  # ✅ Must have Stripe customer ID
        ).all()
        
        # Also get failed renewals ready for retry
        retry_subscriptions = self.db.query(UserSubscription).join(User).filter(
            UserSubscription.active == True,
            UserSubscription.auto_renew == True,
            UserSubscription.renewal_failed == True,
            UserSubscription.renewal_attempts < self.max_retry_attempts,
            UserSubscription.last_renewal_attempt <= datetime.utcnow() - timedelta(days=self.retry_delay_days),
            UserSubscription.payment_method_id.isnot(None),
            User.auto_renew_enabled == True,
            User.stripe_customer_id.isnot(None)
        ).all()
        
        return list(set(subscriptions + retry_subscriptions))
    
    def process_subscription_renewal(self, subscription: UserSubscription) -> bool:
        """Process renewal for a single subscription using saved payment method"""
        user = subscription.user
        plan = subscription.plan
        
        logger.info(f"🔄 Processing renewal for {user.email} - {plan.name} ({subscription.billing_cycle.value})")
        
        # Verify payment method still exists
        if not self.verify_payment_method_exists(user.stripe_customer_id, subscription.payment_method_id):
            logger.error(f"❌ Payment method {subscription.payment_method_id} no longer exists")
            self.handle_missing_payment_method(subscription)
            return False
        
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
            # Create PaymentIntent with saved payment method
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                customer=user.stripe_customer_id,
                payment_method=subscription.payment_method_id,
                confirmation_method='automatic',
                confirm=True,
                off_session=True,  # ✅ Critical for automated renewals
                metadata={
                    'type': 'renewal',
                    'user_id': str(user.id),
                    'subscription_id': str(subscription.id),
                    'plan_name': plan.name,
                    'billing_cycle': subscription.billing_cycle.value
                }
            )
            
            if payment_intent.status == 'succeeded':
                # Payment successful - extend subscription
                self.extend_subscription(subscription, renewal_period_days, payment_intent)
                
                # Create payment history record
                self.create_renewal_payment_record(subscription, payment_intent, amount)
                
                # Send success notification
                self.send_renewal_success_email(user, plan, subscription.billing_cycle.value, amount)
                
                # Reset failure tracking
                subscription.renewal_failed = False
                subscription.failure_reason = None
                subscription.renewal_attempts = 0
                
                self.db.commit()
                logger.info(f"✅ Renewal payment successful: {payment_intent.id}")
                return True
            
            else:
                # Payment requires action or failed
                error_message = f"Payment status: {payment_intent.status}"
                self.handle_renewal_failure(subscription, error_message, 'payment_incomplete')
                self.db.commit()
                return False
                
        except stripe.error.CardError as e:
            # Card was declined
            logger.warning(f"⚠️ Card declined for renewal: {e.user_message}")
            self.handle_renewal_failure(subscription, e.user_message, 'card_declined')
            self.db.commit()
            return False
            
        except stripe.error.AuthenticationError as e:
            logger.error(f"❌ Stripe authentication error: {e}")
            self.handle_renewal_failure(subscription, "Payment service authentication failed", 'auth_error')
            self.db.commit()
            return False
            
        except stripe.error.InvalidRequestError as e:
            logger.error(f"❌ Invalid request to Stripe: {e}")
            self.handle_renewal_failure(subscription, str(e), 'invalid_request')
            self.db.commit()
            return False
            
        except Exception as e:
            logger.error(f"❌ Exception during renewal for {user.email}: {e}")
            self.handle_renewal_failure(subscription, str(e), 'exception')
            self.db.commit()
            return False
    
    def verify_payment_method_exists(self, customer_id: str, payment_method_id: str) -> bool:
        """Verify that payment method still exists and is attached to customer"""
        try:
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            return payment_method.customer == customer_id
        except stripe.error.InvalidRequestError:
            return False
        except Exception:
            return False
    
    def handle_missing_payment_method(self, subscription: UserSubscription):
        """Handle case where payment method no longer exists"""
        subscription.renewal_failed = True
        subscription.failure_reason = "Payment method no longer available"
        subscription.auto_renew = False  # Disable auto-renewal
        
        user = subscription.user
        plan = subscription.plan
        
        # Send email notification
        self.send_missing_payment_method_email(user, plan)
        
        logger.warning(f"⚠️ Disabled auto-renewal for {user.email} - payment method missing")
    
    def extend_subscription(self, subscription: UserSubscription, days: int, payment_intent):
        """Extend subscription period"""
        new_expiry = subscription.expiry_date + timedelta(days=days)
        subscription.expiry_date = new_expiry
        subscription.next_renewal_date = new_expiry
        subscription.last_payment_date = datetime.utcnow()
        subscription.last_payment_intent_id = payment_intent.id
        
        # Reset usage counters for new period
        subscription.queries_used = 0
        subscription.documents_uploaded = 0
        
        logger.info(f"✅ Subscription extended until: {new_expiry}")
    
    def create_renewal_payment_record(self, subscription: UserSubscription, payment_intent, amount: int):
        """Create payment history record for renewal"""
        payment_record = PaymentHistory(
            user_id=subscription.user_id,
            subscription_id=subscription.id,
            payment_intent_id=payment_intent.id,
            amount=amount,
            currency='usd',
            status='succeeded',
            billing_cycle=subscription.billing_cycle,
            is_renewal=True,
            payment_date=datetime.utcnow(),
            meta_info=f"Automatic renewal - Payment Method: {subscription.payment_method_id[-4:]}"
        )
        self.db.add(payment_record)
        logger.info(f"✅ Renewal payment record created")
    
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
        
        subject = f"✅ {plan.name} Plan Renewed Successfully"
        body = f"""
Hi {user.full_name},

Great news! Your {plan.name} plan has been automatically renewed.

💳 Payment Details:
- Plan: {plan.name}
- Billing: {billing_cycle.title()}
- Amount: ${amount / 100:.2f}
- Payment Method: ****{user.default_payment_method_id[-4:] if user.default_payment_method_id else 'xxxx'}
- Next Renewal: {(datetime.utcnow() + timedelta(days=365 if billing_cycle == 'yearly' else 30)).strftime('%B %d, %Y')}

Your subscription continues uninterrupted. Thank you for using SuperEngineer!

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Renewal success email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send renewal success email: {e}")
    
    def send_renewal_failed_retry_email(self, user: User, plan, error_message: str, next_retry: datetime):
        """Send renewal failure notification with retry info"""
        if not user.email_notifications:
            return
        
        subject = f"⚠️ Payment Issue - {plan.name} Plan Renewal"
        body = f"""
Hi {user.full_name},

We encountered an issue while renewing your {plan.name} plan:

❌ Issue: {error_message}

Don't worry! We'll automatically retry the payment on {next_retry.strftime('%B %d, %Y')}.

If you'd like to update your payment method or renew manually, please log in to your account.

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Renewal retry email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send renewal retry email: {e}")
    
    def send_renewal_failed_final_email(self, user: User, plan, error_message: str):
        """Send final renewal failure notification"""
        if not user.email_notifications:
            return
        
        subject = f"🚨 Action Required - {plan.name} Plan Renewal Failed"
        body = f"""
Hi {user.full_name},

We were unable to renew your {plan.name} plan after multiple attempts:

❌ Final Error: {error_message}

⚠️ Your subscription will expire soon. To continue using SuperEngineer:

1. Log in to your account
2. Update your payment method
3. Manually renew your subscription

We've temporarily disabled auto-renewal for your account. You can re-enable it after updating your payment method.

Need help? Contact our support team.

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Final renewal failure email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send final renewal failure email: {e}")
    
    def send_missing_payment_method_email(self, user: User, plan):
        """Send notification when payment method is missing"""
        if not user.email_notifications:
            return
        
        subject = f"💳 Payment Method Required - {plan.name} Plan"
        body = f"""
Hi {user.full_name},

We noticed that your saved payment method is no longer available for your {plan.name} plan.

To continue enjoying uninterrupted service:

1. Log in to your account
2. Add a new payment method
3. Re-enable auto-renewal

Your subscription is still active, but we've temporarily disabled auto-renewal until you update your payment method.

Best regards,
The SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Missing payment method email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send missing payment method email: {e}")
    
    def send_renewal_summary(self, success_count: int, failure_count: int):
        """Send renewal summary to admin"""
        if success_count == 0 and failure_count == 0:
            return
        
        subject = f"🔄 Enhanced Renewal Summary - {datetime.utcnow().strftime('%Y-%m-%d')}"
        body = f"""
Enhanced Renewal Process Summary:

✅ Successful Renewals: {success_count}
❌ Failed Renewals: {failure_count}
📅 Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}
💳 Method: Saved Payment Methods

Total Processed: {success_count + failure_count}
Success Rate: {(success_count / (success_count + failure_count) * 100):.1f}%

📊 System Status: Enhanced renewal service with saved payment methods working correctly.
        """
        
        # Send to admin email (configure in environment)
        admin_email = os.getenv("ADMIN_EMAIL", "admin@superengineer.com")
        try:
            send_email(admin_email, subject, body)
            logger.info("📧 Renewal summary sent to admin")
        except Exception as e:
            logger.error(f"❌ Failed to send renewal summary: {e}")

# ✅ Standalone script to run the enhanced renewal service
def run_enhanced_renewal_service():
    """Entry point for cron job - Enhanced version"""
    try:
        logger.info("🚀 Starting Enhanced Renewal Service with Saved Payment Methods")
        service = EnhancedRenewalService()
        service.run_renewal_check()
        logger.info("✅ Enhanced Renewal Service completed successfully")
    except Exception as e:
        logger.error(f"❌ Enhanced Renewal Service failed: {e}")

if __name__ == "__main__":
    import os
    run_enhanced_renewal_service()