# app/routers/webhook.py - Updated for one-time payments

import stripe
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from app.config import STRIPE_WEBHOOK_SECRET
from app.db.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.subscription import UserSubscription, PaymentHistory, BillingCycle, SubscriptionPlan
from app.utils.email import send_email
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Stripe Webhook"])

@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
):
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
            # Handle successful checkout for one-time payment
            handle_checkout_completed(data, db)
            
        elif event_type == "payment_intent.succeeded":
            # Handle successful payment (includes renewals)
            handle_payment_succeeded(data, db)
            
        elif event_type == "payment_intent.payment_failed":
            # Handle failed payment
            handle_payment_failed(data, db)
            
        elif event_type == "payment_method.attached":
            # Handle payment method attached to customer
            handle_payment_method_attached(data, db)
            
        elif event_type == "customer.updated":
            # Handle customer updates
            handle_customer_updated(data, db)
            
        else:
            logger.info(f"ℹ️ Unhandled webhook event: {event_type}")

    except Exception as e:
        logger.error(f"❌ Error processing webhook {event_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")

    return {"status": "success"}

def handle_checkout_completed(session_data, db: Session):
    """Handle completed checkout session for initial subscription"""
    customer_id = session_data.get('customer')
    payment_intent_id = session_data.get('payment_intent')
    metadata = session_data.get('metadata', {})
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.error(f"❌ User not found for customer {customer_id}")
        return
    
    # Get payment intent to extract payment method
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        payment_method_id = payment_intent.payment_method
        amount = payment_intent.amount
    except Exception as e:
        logger.error(f"❌ Error retrieving payment intent {payment_intent_id}: {e}")
        return
    
    # Extract plan information from metadata
    plan_name = metadata.get('plan_name')
    billing_cycle = metadata.get('billing_cycle', 'monthly')
    
    if not plan_name:
        logger.error("❌ Plan name not found in checkout session metadata")
        return
    
    # Get plan from database
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name.ilike(plan_name)).first()
    if not plan:
        logger.error(f"❌ Plan not found: {plan_name}")
        return
    
    # Create or update subscription
    try:
        activate_user_subscription(
            user=user,
            plan=plan,
            billing_cycle=billing_cycle,
            payment_intent_id=payment_intent_id,
            payment_method_id=payment_method_id,
            amount=amount,
            db=db
        )
        
        logger.info(f"✅ Subscription activated for {user.email} - {plan_name} ({billing_cycle})")
        
        # Send welcome email
        send_subscription_welcome_email(user, plan, billing_cycle)
        
    except Exception as e:
        logger.error(f"❌ Error activating subscription for {user.email}: {e}")

def handle_payment_succeeded(payment_intent_data, db: Session):
    """Handle successful payment (renewal or initial)"""
    customer_id = payment_intent_data.get('customer')
    payment_intent_id = payment_intent_data['id']
    amount = payment_intent_data['amount']
    metadata = payment_intent_data.get('metadata', {})
    
    # Check if this is a renewal payment
    if metadata.get('type') == 'renewal':
        handle_renewal_payment_success(payment_intent_data, db)
        return
    
    # For non-renewal payments, log for tracking
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        logger.info(f"✅ Payment succeeded for {user.email}: ${amount/100:.2f}")

def handle_renewal_payment_success(payment_intent_data, db: Session):
    """Handle successful renewal payment"""
    metadata = payment_intent_data.get('metadata', {})
    subscription_id = metadata.get('subscription_id')
    
    if not subscription_id:
        logger.error("❌ Subscription ID not found in renewal payment metadata")
        return
    
    subscription = db.query(UserSubscription).filter(UserSubscription.id == int(subscription_id)).first()
    if not subscription:
        logger.error(f"❌ Subscription not found: {subscription_id}")
        return
    
    # The renewal service should have already processed this
    # This webhook serves as confirmation
    logger.info(f"✅ Renewal payment confirmed for subscription {subscription_id}")

def handle_payment_failed(payment_intent_data, db: Session):
    """Handle failed payment"""
    customer_id = payment_intent_data.get('customer')
    payment_intent_id = payment_intent_data['id']
    metadata = payment_intent_data.get('metadata', {})
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.error(f"❌ User not found for customer {customer_id}")
        return
    
    # Check if this is a renewal payment failure
    if metadata.get('type') == 'renewal':
        subscription_id = metadata.get('subscription_id')
        if subscription_id:
            subscription = db.query(UserSubscription).filter(
                UserSubscription.id == int(subscription_id)
            ).first()
            
            if subscription:
                logger.warning(f"⚠️ Renewal payment failed for {user.email} - subscription {subscription_id}")
                # The renewal service will handle retries
                return
    
    # For other payment failures, send notification
    logger.warning(f"⚠️ Payment failed for {user.email}: {payment_intent_id}")
    send_payment_failed_email(user, payment_intent_data)

def handle_payment_method_attached(payment_method_data, db: Session):
    """Handle payment method attached to customer"""
    customer_id = payment_method_data.get('customer')
    payment_method_id = payment_method_data['id']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    
    # Set as default payment method if user doesn't have one
    if not user.default_payment_method_id:
        user.default_payment_method_id = payment_method_id
        db.commit()
        logger.info(f"✅ Set default payment method for {user.email}: {payment_method_id}")

def handle_customer_updated(customer_data, db: Session):
    """Handle customer updates"""
    customer_id = customer_data['id']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        logger.info(f"ℹ️ Customer updated: {user.email}")

def activate_user_subscription(
    user: User,
    plan: SubscriptionPlan,
    billing_cycle: str,
    payment_intent_id: str,
    payment_method_id: str,
    amount: int,
    db: Session
):
    """Activate subscription for user"""
    # Deactivate existing subscriptions
    existing_subscriptions = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).all()
    
    for sub in existing_subscriptions:
        sub.active = False
    
    # Calculate expiry date
    if billing_cycle == "yearly":
        expiry_date = datetime.utcnow() + timedelta(days=365)
    else:
        expiry_date = datetime.utcnow() + timedelta(days=30)
    
    # Create new subscription
    new_subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        active=True,
        billing_cycle=BillingCycle(billing_cycle),
        start_date=datetime.utcnow(),
        expiry_date=expiry_date,
        next_renewal_date=expiry_date,
        auto_renew=user.auto_renew_enabled,
        queries_used=0,
        documents_uploaded=0,
        last_payment_date=datetime.utcnow(),
        last_payment_intent_id=payment_intent_id,
        payment_method_id=payment_method_id,
        renewal_attempts=0,
        renewal_failed=False
    )
    db.add(new_subscription)
    
    # Update user's default payment method
    if payment_method_id:
        user.default_payment_method_id = payment_method_id
    
    # Create payment history record
    payment_record = PaymentHistory(
        user_id=user.id,
        subscription_id=new_subscription.id,
        payment_intent_id=payment_intent_id,
        amount=amount,
        status="succeeded",
        billing_cycle=BillingCycle(billing_cycle),
        is_renewal=False
    )
    db.add(payment_record)
    
    db.commit()

def send_subscription_welcome_email(user: User, plan: SubscriptionPlan, billing_cycle: str):
    """Send welcome email for new subscription"""
    if not user.email_notifications:
        return
    
    subject = f"Welcome to {plan.name} Plan!"
    body = f"""
Hi {user.full_name},

Welcome to the {plan.name} plan! Your subscription is now active.

Plan Details:
- Plan: {plan.name}
- Billing: {billing_cycle.title()}
- Queries: {plan.query_limit if plan.query_limit > 0 else 'Unlimited'} per month
- Document Uploads: {plan.document_upload_limit} per month
- Ninja Mode: {'✅' if plan.ninja_mode else '❌'}
- Meme Generator: {'✅' if plan.meme_generator else '❌'}

Your subscription will automatically renew unless you choose to disable auto-renewal in your account settings.

Thank you for choosing SuperEngineer!

Best regards,
The SuperEngineer Team
    """
    
    try:
        send_email(user.email, subject, body)
        logger.info(f"📧 Welcome email sent to {user.email}")
    except Exception as e:
        logger.error(f"❌ Failed to send welcome email to {user.email}: {e}")

def send_payment_failed_email(user: User, payment_intent_data: dict):
    """Send payment failure notification"""
    if not user.email_notifications:
        return
    
    subject = "Payment Failed - Action Required"
    body = f"""
Hi {user.full_name},

We encountered an issue processing your payment:

Payment ID: {payment_intent_data['id']}
Amount: ${payment_intent_data['amount']/100:.2f}

Please update your payment method in your account settings to continue using SuperEngineer.

Best regards,
The SuperEngineer Team
    """
    
    try:
        send_email(user.email, subject, body)
        logger.info(f"📧 Payment failure email sent to {user.email}")
    except Exception as e:
        logger.error(f"❌ Failed to send payment failure email to {user.email}: {e}")