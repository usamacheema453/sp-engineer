# app/utils/renewal_service_5min.py - Updated for 5-minute cron job

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.user import User
from app.models.subscription import UserSubscription, PaymentHistory, BillingCycle
from app.utils.email import send_email
import stripe
import logging
import os
from app.config import STRIPE_SECRET_KEY

# Configure logging for 5-min intervals
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/renewal_5min.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

class FiveMinuteRenewalService:
    def __init__(self):
        self.db = SessionLocal()
        self.max_retry_attempts = 3
        self.retry_delay_minutes = 10  # ✅ Changed from days to minutes for testing
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def run_renewal_check(self):
        """Main method for 5-minute interval renewal checks"""
        logger.info("🚀 Starting 5-Minute Renewal Service...")
        
        try:
            # Get subscriptions that need renewal (more aggressive for testing)
            subscriptions_to_renew = self.get_subscriptions_for_renewal()
            logger.info(f"📊 Found {len(subscriptions_to_renew)} subscriptions to process")
            
            if len(subscriptions_to_renew) == 0:
                logger.info("✅ No subscriptions need renewal at this time")
                return
            
            success_count = 0
            failure_count = 0
            
            for subscription in subscriptions_to_renew:
                try:
                    logger.info(f"🔄 Processing subscription ID: {subscription.id} for user: {subscription.user.email}")
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
            
            # Log summary
            logger.info(f"📈 Renewal Summary - Success: {success_count}, Failures: {failure_count}")
            
        except Exception as e:
            logger.error(f"❌ Critical error in 5-minute renewal check: {e}")
        finally:
            self.db.close()
    
    def get_subscriptions_for_renewal(self):
        """Get subscriptions that need renewal - optimized for 5-minute intervals"""
        # ✅ More aggressive renewal window for testing (next 10 minutes)
        renewal_threshold = datetime.utcnow() + timedelta(minutes=10)
        
        logger.info(f"🔍 Looking for subscriptions expiring before: {renewal_threshold}")
        
        subscriptions = self.db.query(UserSubscription).join(User).filter(
            UserSubscription.active == True,
            UserSubscription.auto_renew == True,
            UserSubscription.renewal_failed == False,
            UserSubscription.next_renewal_date <= renewal_threshold,
            UserSubscription.payment_method_id.isnot(None),  # Must have saved payment method
            User.auto_renew_enabled == True,
            User.stripe_customer_id.isnot(None)
        ).all()
        
        logger.info(f"📊 Found {len(subscriptions)} subscriptions ready for renewal")
        
        # Also get failed renewals ready for retry (retry after 10 minutes)
        retry_threshold = datetime.utcnow() - timedelta(minutes=self.retry_delay_minutes)
        retry_subscriptions = self.db.query(UserSubscription).join(User).filter(
            UserSubscription.active == True,
            UserSubscription.auto_renew == True,
            UserSubscription.renewal_failed == True,
            UserSubscription.renewal_attempts < self.max_retry_attempts,
            UserSubscription.last_renewal_attempt <= retry_threshold,
            UserSubscription.payment_method_id.isnot(None),
            User.auto_renew_enabled == True,
            User.stripe_customer_id.isnot(None)
        ).all()
        
        logger.info(f"📊 Found {len(retry_subscriptions)} subscriptions ready for retry")
        
        return list(set(subscriptions + retry_subscriptions))
    
    def process_subscription_renewal(self, subscription: UserSubscription) -> bool:
        """Process renewal for a single subscription"""
        user = subscription.user
        plan = subscription.plan
        
        logger.info(f"💳 Processing renewal: {user.email} - {plan.name} ({subscription.billing_cycle.value})")
        
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
        
        logger.info(f"💰 Renewal amount: ${amount/100:.2f}")
        
        # Update renewal attempt tracking
        subscription.renewal_attempts += 1
        subscription.last_renewal_attempt = datetime.utcnow()
        
        try:
            # Create PaymentIntent with saved payment method
            logger.info(f"🔄 Creating payment intent with saved method: {subscription.payment_method_id}")
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                customer=user.stripe_customer_id,
                payment_method=subscription.payment_method_id,
                confirmation_method='automatic',
                confirm=True,
                off_session=True,  # Critical for automated renewals
                metadata={
                    'type': 'renewal',
                    'user_id': str(user.id),
                    'subscription_id': str(subscription.id),
                    'plan_name': plan.name,
                    'billing_cycle': subscription.billing_cycle.value,
                    'renewal_service': '5_minute_interval'
                }
            )
            
            logger.info(f"💳 Payment intent created: {payment_intent.id}, Status: {payment_intent.status}")
            
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
                logger.warning(f"⚠️ Payment incomplete: {error_message}")
                self.handle_renewal_failure(subscription, error_message, 'payment_incomplete')
                self.db.commit()
                return False
                
        except stripe.error.CardError as e:
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
        """Verify that payment method still exists"""
        try:
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            is_valid = payment_method.customer == customer_id
            logger.info(f"🔍 Payment method verification: {payment_method_id} - Valid: {is_valid}")
            return is_valid
        except stripe.error.InvalidRequestError:
            logger.warning(f"⚠️ Payment method not found: {payment_method_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Error verifying payment method: {e}")
            return False
    
    def extend_subscription(self, subscription: UserSubscription, days: int, payment_intent):
        """Extend subscription period"""
        old_expiry = subscription.expiry_date
        new_expiry = subscription.expiry_date + timedelta(days=days)
        
        subscription.expiry_date = new_expiry
        subscription.next_renewal_date = new_expiry
        subscription.last_payment_date = datetime.utcnow()
        subscription.last_payment_intent_id = payment_intent.id
        
        # Reset usage counters for new period
        subscription.queries_used = 0
        subscription.documents_uploaded = 0
        
        logger.info(f"📅 Subscription extended: {old_expiry} → {new_expiry}")
    
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
            meta_info=f"5-minute renewal service - PM: {subscription.payment_method_id[-4:]}"
        )
        self.db.add(payment_record)
        logger.info(f"📝 Payment history record created")
    
    def handle_renewal_failure(self, subscription: UserSubscription, error_message: str, error_type: str):
        """Handle renewal failure"""
        subscription.renewal_failed = True
        subscription.failure_reason = error_message
        
        user = subscription.user
        plan = subscription.plan
        
        logger.warning(f"⚠️ Renewal failure handled: {error_type} - {error_message}")
        
        # Check if we've reached max retry attempts
        if subscription.renewal_attempts >= self.max_retry_attempts:
            logger.warning(f"⚠️ Max retry attempts reached for {user.email}. Disabling auto-renewal.")
            subscription.auto_renew = False
            self.send_renewal_failed_final_email(user, plan, error_message)
        else:
            # Send retry notification
            next_retry = datetime.utcnow() + timedelta(minutes=self.retry_delay_minutes)
            logger.info(f"🔄 Will retry renewal at: {next_retry}")
            self.send_renewal_failed_retry_email(user, plan, error_message, next_retry)
    
    def handle_missing_payment_method(self, subscription: UserSubscription):
        """Handle case where payment method no longer exists"""
        subscription.renewal_failed = True
        subscription.failure_reason = "Payment method no longer available"
        subscription.auto_renew = False
        
        user = subscription.user
        plan = subscription.plan
        
        self.send_missing_payment_method_email(user, plan)
        logger.warning(f"⚠️ Disabled auto-renewal for {user.email} - payment method missing")
    
    def send_renewal_success_email(self, user: User, plan, billing_cycle: str, amount: int):
        """Send renewal success notification"""
        if not user.email_notifications:
            logger.info(f"📧 Skipping email notification (user preference): {user.email}")
            return
        
        subject = f"✅ {plan.name} Plan Renewed Successfully (5-Min Service)"
        body = f"""
Hi {user.full_name},

Your {plan.name} plan has been automatically renewed by our 5-minute renewal service.

💳 Payment Details:
- Plan: {plan.name}
- Amount: ${amount / 100:.2f}
- Billing: {billing_cycle.title()}
- Processed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

Next renewal: {(datetime.utcnow() + timedelta(days=365 if billing_cycle == 'yearly' else 30)).strftime('%B %d, %Y')}

Best regards,
SuperEngineer Team
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
        
        subject = f"⚠️ Payment Issue - {plan.name} Plan (Will Retry)"
        body = f"""
Hi {user.full_name},

We encountered an issue while renewing your {plan.name} plan:

❌ Issue: {error_message}

🔄 We'll retry the payment at: {next_retry.strftime('%Y-%m-%d %H:%M:%S')}

Our 5-minute renewal service will automatically attempt renewal again.

Best regards,
SuperEngineer Team
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

⚠️ Auto-renewal has been disabled. Please:
1. Log in to your account
2. Update your payment method
3. Manually renew your subscription

Best regards,
SuperEngineer Team
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

Your saved payment method is no longer available for your {plan.name} plan.

Please log in and add a new payment method to continue service.

Best regards,
SuperEngineer Team
        """
        
        try:
            send_email(user.email, subject, body)
            logger.info(f"📧 Missing payment method email sent to {user.email}")
        except Exception as e:
            logger.error(f"❌ Failed to send missing payment method email: {e}")

# ✅ Entry point for 5-minute cron job
def run_5_minute_renewal_service():
    """Entry point for 5-minute interval cron job"""
    try:
        logger.info("🚀 Starting 5-Minute Renewal Service")
        service = FiveMinuteRenewalService()
        service.run_renewal_check()
        logger.info("✅ 5-Minute Renewal Service completed")
    except Exception as e:
        logger.error(f"❌ 5-Minute Renewal Service failed: {e}")

if __name__ == "__main__":
    run_5_minute_renewal_service()