# app/routers/simple_payment.py - Simple Stripe method without webhooks

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from datetime import datetime, timedelta
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription, BillingCycle
from app.utils.stripe_service import create_customer, get_payment_intent
from pydantic import BaseModel, EmailStr
import stripe
from app.config import STRIPE_SECRET_KEY

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/simple-payments", tags=["Simple Payments"])

class SimpleCheckoutRequest(BaseModel):
    email: EmailStr
    plan_id: int
    billing_cycle: str  # "monthly" or "yearly"

class ConfirmPaymentRequest(BaseModel):
    email: EmailStr
    payment_intent_id: str

# ✅ 1. Create Payment Intent (Simple Method)
@router.post("/create-payment-intent")
def create_simple_payment_intent(request: SimpleCheckoutRequest, db: Session = Depends(get_db)):
    """Create payment intent for simple one-time payment"""
    
    try:
        # Get user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create Stripe customer if not exists
        if not user.stripe_customer_id:
            customer_id = create_customer(request.email)
            user.stripe_customer_id = customer_id
            db.commit()
        
        # Get plan
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == request.plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Calculate amount
        if request.billing_cycle == "yearly":
            amount = plan.yearly_price
        else:
            amount = plan.monthly_price
        
        if not amount:
            raise HTTPException(status_code=400, detail="Price not configured")
        
        # Create PaymentIntent directly (simple method)
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            customer=user.stripe_customer_id,
            automatic_payment_methods={'enabled': True},
            setup_future_usage='off_session',  # Save payment method for renewals
            metadata={
                'user_email': request.email,
                'plan_id': str(request.plan_id),
                'plan_name': plan.name,
                'billing_cycle': request.billing_cycle
            }
        )
        
        return {
            "payment_intent_id": payment_intent.id,
            "client_secret": payment_intent.client_secret,
            "amount": amount,
            "currency": "usd",
            "plan_name": plan.name,
            "billing_cycle": request.billing_cycle
        }
        
    except Exception as e:
        print(f"❌ Payment intent creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 2. Confirm Payment (Manual Check - No Webhook Needed)
@router.post("/confirm-payment")
def confirm_simple_payment(request: ConfirmPaymentRequest, db: Session = Depends(get_db)):
    """Manually confirm payment and activate subscription"""
    
    try:
        # Get user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get payment intent details from Stripe
        payment_intent = stripe.PaymentIntent.retrieve(request.payment_intent_id)
        
        # Check if payment was successful
        if payment_intent.status != 'succeeded':
            raise HTTPException(
                status_code=400, 
                detail=f"Payment not completed. Status: {payment_intent.status}"
            )
        
        # Extract metadata
        metadata = payment_intent.metadata
        plan_id = int(metadata.get('plan_id'))
        billing_cycle = metadata.get('billing_cycle', 'monthly')
        
        # Get plan
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Deactivate existing subscriptions
        existing_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).all()
        
        for sub in existing_subs:
            sub.active = False
        
        # Calculate expiry
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
            auto_renew=True,
            queries_used=0,
            documents_uploaded=0,
            last_payment_date=datetime.utcnow(),
            last_payment_intent_id=payment_intent.id,
            payment_method_id=payment_intent.payment_method,  # Save payment method
            renewal_attempts=0,
            renewal_failed=False
        )
        
        db.add(new_subscription)
        
        # Update user's default payment method
        if payment_intent.payment_method:
            user.default_payment_method_id = payment_intent.payment_method
        
        db.commit()
        
        return {
            "success": True,
            "message": f"{plan.name} plan activated successfully!",
            "subscription": {
                "plan": plan.name,
                "billing_cycle": billing_cycle,
                "expiry_date": expiry_date,
                "amount_paid": payment_intent.amount / 100  # Convert to dollars
            }
        }
        
    except Exception as e:
        print(f"❌ Payment confirmation error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 3. Check Payment Status (Optional - for frontend polling)
@router.get("/payment-status/{payment_intent_id}")
def check_payment_status(payment_intent_id: str):
    """Check payment status without webhooks"""
    
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        return {
            "payment_intent_id": payment_intent.id,
            "status": payment_intent.status,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency,
            "metadata": payment_intent.metadata
        }
        
    except Exception as e:
        print(f"❌ Payment status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 4. Simple subscription check
@router.get("/subscription-status/{email}")
def get_simple_subscription_status(email: str, db: Session = Depends(get_db)):
    """Get current subscription status"""
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()
    
    if subscription:
        return {
            "has_subscription": True,
            "plan": subscription.plan.name,
            "billing_cycle": subscription.billing_cycle.value,
            "expiry_date": subscription.expiry_date,
            "days_remaining": (subscription.expiry_date - datetime.utcnow()).days,
            "auto_renew": subscription.auto_renew
        }
    else:
        return {
            "has_subscription": False,
            "plan": None,  # ✅ Changed from "free" to None
            "requires_plan_selection": True
        }
