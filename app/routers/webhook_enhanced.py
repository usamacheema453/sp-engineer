# app/routers/webhook_enhanced.py - Enhanced webhook to handle payment method saving

import stripe
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from app.config import STRIPE_WEBHOOK_SECRET
from app.db.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.subscription import UserSubscription, PaymentHistory, BillingCycle, SubscriptionPlan
from datetime import datetime, timedelta
import json
import logging
from urllib.parse import unquote
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["Enhanced Stripe Webhook"])

def decode_email(email: str) -> str:
    """Helper function to decode email"""
    try:
        decoded = unquote(email)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, decoded):
            return decoded
        return email
    except Exception as e:
        logger.error(f"Error decoding email {email}: {str(e)}")
        return email

@router.post("/stripe-enhanced")
async def enhanced_stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Enhanced webhook handler that also processes payment method saving"""
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error(f"❌ Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook Error: {str(e)}")

    event_type = event['type']
    data = event['data']['object']
    
    logger.info(f"📥 Received webhook: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            # Handle successful checkout (both regular and with payment method saving)
            handle_enhanced_checkout_completed(data, db)
            
        elif event_type == "payment_intent.succeeded":
            # Handle successful payment (includes payments from saved methods)
            handle_enhanced_payment_succeeded(data, db)
            
        elif event_type == "setup_intent.succeeded":
            # Handle successful payment method setup (card saving without charging)
            handle_setup_intent_succeeded(data, db)
            
        elif event_type == "payment_method.attached":
            # Handle payment method attached to customer
            handle_payment_method_attached(data, db)
            
        elif event_type == "payment_intent.payment_failed":
            # Handle failed payment
            handle_payment_failed(data, db)
            
        else:
            logger.info(f"ℹ️ Unhandled webhook event: {event_type}")

    except Exception as e:
        logger.error(f"❌ Error processing webhook {event_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")

    return {"status": "success"}

def handle_enhanced_checkout_completed(session_data, db: Session):
    """Handle completed checkout session (enhanced version)"""
    try:
        customer_id = session_data.get('customer')
        payment_intent_id = session_data.get('payment_intent')
        metadata = session_data.get('metadata', {})
        
        logger.info(f"🛒 Processing checkout completion: {session_data.get('id')}")
        
        # Get user by customer ID or email
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        
        if not user and metadata.get('user_email'):
            email = decode_email(metadata.get('user_email'))
            user = db.query(User).filter(User.email == email).first()
        
        if not user:
            logger.error(f"❌ User not found for customer {customer_id}")
            return
        
        # Get payment intent details
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            payment_method_id = payment_intent.payment_method
            amount = payment_intent.amount
        except Exception as e:
            logger.error(f"❌ Error retrieving payment intent {payment_intent_id}: {e}")
            return
        
        # Extract plan information
        plan_id = metadata.get('plan_id')
        billing_cycle = metadata.get('billing_cycle', 'monthly')
        save_payment_method = metadata.get('save_payment_method', 'true').lower() == 'true'
        
        if not plan_id:
            logger.error("❌ Plan ID not found in checkout session metadata")
            return
        
        # Get plan from database
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == int(plan_id)).first()
        if not plan:
            logger.error(f"❌ Plan not found: {plan_id}")
            return
        
        logger.info(f"💳 Processing payment: Amount: {amount}, Plan: {plan.name}, Save PM: {save_payment_method}")
        
        # Handle payment method saving
        if save_payment_method and payment_method_id:
            # Set as default if user doesn't have one
            if not user.default_payment_method_id:
                user.default_payment_method_id = payment_method_id
                logger.info(f"✅ Set default payment method: {payment_method_id}")
        
        # Create or update subscription
        subscription = create_or_update_subscription_from_webhook(
            user=user,
            plan=plan,
            billing_cycle=billing_cycle,
            payment_intent_id=payment_intent_id,
            payment_method_id=payment_method_id if save_payment_method else None,
            amount=amount,
            db=db
        )
        
        logger.info(f"✅ Subscription activated: {subscription.id} for user {user.email}")
        
    except Exception as e:
        logger.error(f"❌ Error in checkout completion: {e}")

def handle_enhanced_payment_succeeded(payment_intent_data, db: Session):
    """Handle successful payment intent (enhanced version)"""
    try:
        customer_id = payment_intent_data.get('customer')
        payment_intent_id = payment_intent_data['id']
        amount = payment_intent_data['amount']
        metadata = payment_intent_data.get('metadata', {})
        payment_method_id = payment_intent_data.get('payment_method')
        
        logger.info(f"💳 Payment succeeded: {payment_intent_id}")
        
        # Check if this is a saved payment method charge
        if metadata.get('type') == 'saved_payment_method_charge':
            logger.info("✅ Payment from saved payment method processed")
            return
        
        # Check if this is a renewal payment
        if metadata.get('type') == 'renewal':
            handle_renewal_payment_success(payment_intent_data, db)
            return
        
        # Regular payment processing
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            logger.info(f"✅ Payment confirmed for {user.email}: ${amount/100:.2f}")
            
            # If payment method should be saved (setup_future_usage was used)
            if payment_method_id and payment_intent_data.get('setup_future_usage') == 'off_session':
                if not user.default_payment_method_id:
                    user.default_payment_method_id = payment_method_id
                    db.commit()
                    logger.info(f"✅ Default payment method set from payment: {payment_method_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing payment success: {e}")

def handle_setup_intent_succeeded(setup_intent_data, db: Session):
    """Handle successful setup intent (payment method saved without charging)"""
    try:
        customer_id = setup_intent_data.get('customer')
        payment_method_id = setup_intent_data.get('payment_method')
        metadata = setup_intent_data.get('metadata', {})
        
        logger.info(f"💾 Setup intent succeeded: {setup_intent_data.get('id')}")
        
        if not payment_method_id:
            logger.warning("⚠️ No payment method in setup intent")
            return
        
        # Find user
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        
        if not user and metadata.get('user_id'):
            user = db.query(User).filter(User.id == int(metadata.get('user_id'))).first()
        
        if not user:
            logger.error(f"❌ User not found for setup intent")
            return
        
        # Set as default payment method if user doesn't have one
        if not user.default_payment_method_id:
            user.default_payment_method_id = payment_method_id
            db.commit()
            logger.info(f"✅ Payment method saved and set as default: {payment_method_id}")
        else:
            logger.info(f"✅ Payment method saved: {payment_method_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing setup intent: {e}")

def handle_payment_method_attached(payment_method_data, db: Session):
    """Handle payment method attached to customer"""
    try:
        customer_id = payment_method_data.get('customer')
        payment_method_id = payment_method_data['id']
        
        logger.info(f"🔗 Payment method attached: {payment_method_id}")
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if not user:
            logger.warning(f"⚠️ User not found for customer {customer_id}")
            return
        
        # Set as default if user doesn't have one
        if not user.default_payment_method_id:
            user.default_payment_method_id = payment_method_id
            db.commit()
            logger.info(f"✅ Set as default payment method: {payment_method_id}")
        
    except Exception as e:
        logger.error(f"❌ Error handling payment method attachment: {e}")

def handle_payment_failed(payment_intent_data, db: Session):
    """Handle failed payment"""
    try:
        customer_id = payment_intent_data.get('customer')
        payment_intent_id = payment_intent_data['id']
        metadata = payment_intent_data.get('metadata', {})
        
        logger.warning(f"⚠️ Payment failed: {payment_intent_id}")
        
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if not user:
            logger.error(f"❌ User not found for failed payment")
            return
        
        # Check if this is a renewal payment failure
        if metadata.get('type') == 'renewal':
            subscription_id = metadata.get('subscription_id')
            if subscription_id:
                subscription = db.query(UserSubscription).filter(
                    UserSubscription.id == int(subscription_id)
                ).first()
                
                if subscription:
                    subscription.renewal_failed = True
                    subscription.failure_reason = "Payment failed"
                    subscription.renewal_attempts += 1
                    db.commit()
                    logger.warning(f"⚠️ Renewal payment failed for subscription {subscription_id}")
        
        logger.warning(f"⚠️ Payment failed for user {user.email}")
        
    except Exception as e:
        logger.error(f"❌ Error handling payment failure: {e}")

def handle_renewal_payment_success(payment_intent_data, db: Session):
    """Handle successful renewal payment"""
    try:
        metadata = payment_intent_data.get('metadata', {})
        subscription_id = metadata.get('subscription_id')
        
        if not subscription_id:
            logger.error("❌ Subscription ID not found in renewal payment")
            return
        
        subscription = db.query(UserSubscription).filter(
            UserSubscription.id == int(subscription_id)
        ).first()
        
        if not subscription:
            logger.error(f"❌ Subscription not found: {subscription_id}")
            return
        
        # Reset failure tracking
        subscription.renewal_failed = False
        subscription.failure_reason = None
        subscription.renewal_attempts = 0
        subscription.last_payment_date = datetime.utcnow()
        subscription.last_payment_intent_id = payment_intent_data['id']
        
        # Extend subscription
        if subscription.billing_cycle == BillingCycle.yearly:
            subscription.expiry_date = subscription.expiry_date + timedelta(days=365)
            subscription.next_renewal_date = subscription.expiry_date
        else:
            subscription.expiry_date = subscription.expiry_date + timedelta(days=30)
            subscription.next_renewal_date = subscription.expiry_date
        
        # Reset usage counters
        subscription.queries_used = 0
        subscription.documents_uploaded = 0
        
        db.commit()
        
        logger.info(f"✅ Renewal payment processed for subscription {subscription_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing renewal payment: {e}")

def create_or_update_subscription_from_webhook(
    user: User,
    plan: SubscriptionPlan,
    billing_cycle: str,
    payment_intent_id: str,
    payment_method_id: str,
    amount: int,
    db: Session
) -> UserSubscription:
    """Create or update subscription from webhook data"""
    
    try:
        # Deactivate existing subscriptions
        existing_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).all()
        
        for sub in existing_subs:
            sub.active = False
            logger.info(f"🔄 Deactivated existing subscription: {sub.id}")
        
        # Calculate expiry date
        if billing_cycle == "yearly":
            expiry_date = datetime.utcnow() + timedelta(days=365)
        else:
            expiry_date = datetime.utcnow() + timedelta(days=30)
        
        # Create billing cycle enum
        billing_cycle_enum = BillingCycle.yearly if billing_cycle == "yearly" else BillingCycle.monthly
        
        # Create new subscription
        new_subscription = UserSubscription(
            user_id=user.id,
            plan_id=plan.id,
            active=True,
            billing_cycle=billing_cycle_enum,
            start_date=datetime.utcnow(),
            expiry_date=expiry_date,
            next_renewal_date=expiry_date,
            auto_renew=bool(payment_method_id),  # Enable auto-renewal only if payment method is saved
            queries_used=0,
            documents_uploaded=0,
            last_payment_date=datetime.utcnow(),
            last_payment_intent_id=payment_intent_id,
            payment_method_id=payment_method_id,
            renewal_attempts=0,
            renewal_failed=False
        )
        
        db.add(new_subscription)
        db.commit()
        db.refresh(new_subscription)
        
        # Create payment history record
        create_payment_history_from_webhook(
            user_id=user.id,
            subscription_id=new_subscription.id,
            payment_intent_id=payment_intent_id,
            amount=amount,
            billing_cycle=billing_cycle,
            db=db
        )
        
        logger.info(f"✅ New subscription created: {new_subscription.id}")
        return new_subscription
        
    except Exception as e:
        logger.error(f"❌ Error creating subscription from webhook: {e}")
        db.rollback()
        raise

def create_payment_history_from_webhook(
    user_id: int,
    subscription_id: int,
    payment_intent_id: str,
    amount: int,
    billing_cycle: str,
    db: Session
):
    """Create payment history record from webhook"""
    try:
        billing_cycle_enum = BillingCycle.yearly if billing_cycle == "yearly" else BillingCycle.monthly
        
        payment_record = PaymentHistory(
            user_id=user_id,
            subscription_id=subscription_id,
            payment_intent_id=payment_intent_id,
            amount=amount,
            currency='usd',
            status='succeeded',
            billing_cycle=billing_cycle_enum,
            payment_date=datetime.utcnow(),
            is_renewal=False,
            meta_info=f"Processed via webhook - Amount: {amount/100:.2f} USD"
        )
        
        db.add(payment_record)
        db.commit()
        
        logger.info(f"✅ Payment history created: {payment_record.id}")
        
    except Exception as e:
        logger.error(f"❌ Error creating payment history: {e}")
        db.rollback()