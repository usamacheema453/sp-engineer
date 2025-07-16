# app/routers/subscription.py - Updated for one-time payments

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from datetime import datetime, timedelta
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription, BillingCycle
from app.utils.stripe_service import (
    create_customer, 
    create_payment_intent,
    get_payment_intent_details,
    get_customer_payment_methods
)
from pydantic import BaseModel, EmailStr
import stripe
from app.config import STRIPE_SECRET_KEY

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/subscriptions", tags=["Subscription"])

# ✅ Request schemas
class CreatePaymentRequest(BaseModel):
    email: EmailStr
    plan_id: int
    billing_cycle: str  # "monthly" or "yearly"

class ConfirmPaymentRequest(BaseModel):
    email: EmailStr
    payment_intent_id: str

class UpdateAutoRenewRequest(BaseModel):
    email: EmailStr
    auto_renew: bool

# ✅ 1. CREATE PAYMENT INTENT (Simple Method)
@router.post("/create-payment")
def create_subscription_payment(request: CreatePaymentRequest, db: Session = Depends(get_db)):
    """Create payment intent for subscription"""
    try:
        # Get user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Create Stripe customer if needed
        if not user.stripe_customer_id or user.stripe_customer_id.startswith('cus_mock'):
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
            raise HTTPException(status_code=400, detail="Price not configured for this plan")
        
        # Create payment intent
        payment_data = create_payment_intent(
            customer_id=user.stripe_customer_id,
            amount=amount,
            plan_name=plan.name,
            billing_cycle=request.billing_cycle,
            user_email=request.email,
            plan_id=request.plan_id
        )
        
        return {
            "success": True,
            "payment_intent_id": payment_data["payment_intent_id"],
            "client_secret": payment_data["client_secret"],
            "amount": amount,
            "plan_name": plan.name,
            "billing_cycle": request.billing_cycle
        }
        
    except Exception as e:
        print(f"❌ Create payment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 2. CONFIRM PAYMENT AND ACTIVATE SUBSCRIPTION
@router.post("/confirm-payment")
def confirm_subscription_payment(request: ConfirmPaymentRequest, db: Session = Depends(get_db)):
    """Confirm payment and activate subscription"""
    try:
        # Get user
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get payment intent details
        payment_details = get_payment_intent_details(request.payment_intent_id)
        if not payment_details:
            raise HTTPException(status_code=400, detail="Invalid payment intent")
        
        # Check payment status
        if payment_details["status"] != "succeeded":
            raise HTTPException(
                status_code=400, 
                detail=f"Payment not completed. Status: {payment_details['status']}"
            )
        
        # Extract plan info from metadata
        metadata = payment_details.get("metadata", {})
        plan_id = int(metadata.get("plan_id", 0))
        billing_cycle = metadata.get("billing_cycle", "monthly")
        
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
            payment_intent_id=request.payment_intent_id,
            payment_method_id=payment_details.get("payment_method"),
            renewal_attempts=0,
            renewal_failed=False
        )
        
        db.add(new_subscription)
        
        # Update user's default payment method
        if payment_details.get("payment_method"):
            user.default_payment_method_id = payment_details["payment_method"]
        
        db.commit()
        
        return {
            "success": True,
            "message": f"{plan.name} plan activated successfully!",
            "subscription": {
                "plan": plan.name,
                "billing_cycle": billing_cycle,
                "expiry_date": expiry_date,
                "amount_paid": payment_details["amount"] / 100
            }
        }
        
    except Exception as e:
        print(f"❌ Confirm payment error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ✅ 3. GET SUBSCRIPTION PLANS
@router.get("/plans")
def get_subscription_plans(db: Session = Depends(get_db)):
    """Get all available subscription plans"""
    plans = db.query(SubscriptionPlan).all()
    
    formatted_plans = []
    for plan in plans:
        formatted_plans.append({
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "monthly_price": plan.monthly_price,  # Price in cents
            "yearly_price": plan.yearly_price,    # Price in cents
            "monthly_price_display": f"${plan.monthly_price / 100:.2f}" if plan.monthly_price else "Free",
            "yearly_price_display": f"${plan.yearly_price / 100:.2f}" if plan.yearly_price else "Free",
            "query_limit": plan.query_limit,
            "document_upload_limit": plan.document_upload_limit,
            "ninja_mode": plan.ninja_mode,
            "meme_generator": plan.meme_generator,
            "features": {
                "queries": f"{plan.query_limit} queries/month" if plan.query_limit > 0 else "Unlimited queries",
                "documents": f"{plan.document_upload_limit} uploads/month" if plan.document_upload_limit > 0 else "No uploads",
                "ninja_mode": plan.ninja_mode,
                "meme_generator": plan.meme_generator
            }
        })
    
    return {"plans": formatted_plans}

# ✅ 4. GET CURRENT SUBSCRIPTION
@router.get("/current/{email}")
def get_current_subscription(email: str, db: Session = Depends(get_db)):
    """Get user's current subscription status"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()
    
    if subscription:
        days_remaining = (subscription.expiry_date - datetime.utcnow()).days
        return {
            "has_subscription": True,
            "plan": subscription.plan.name.lower(),
            "plan_display": subscription.plan.name,
            "billing_cycle": subscription.billing_cycle.value,
            "expiry_date": subscription.expiry_date,
            "days_remaining": max(0, days_remaining),
            "auto_renew": subscription.auto_renew,
            "queries_used": subscription.queries_used,
            "queries_remaining": max(0, subscription.plan.query_limit - subscription.queries_used) if subscription.plan.query_limit > 0 else "unlimited",
            "documents_uploaded": subscription.documents_uploaded,
            "documents_remaining": max(0, subscription.plan.document_upload_limit - subscription.documents_uploaded),
            "renewal_failed": subscription.renewal_failed
        }
    else:
        return {
            "has_subscription": False,
            "plan": "free",
            "plan_display": "Free",
            "queries_remaining": 10,  # Free plan limit
            "documents_remaining": 0
        }

# ✅ 5. UPDATE AUTO-RENEWAL PREFERENCE
@router.post("/update-auto-renew")
def update_auto_renew(request: UpdateAutoRenewRequest, db: Session = Depends(get_db)):
    """Update auto-renewal preference"""
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user's global preference
    user.auto_renew_enabled = request.auto_renew
    
    # Update current subscription
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()
    
    if subscription:
        subscription.auto_renew = request.auto_renew
        # Reset failure status if enabling
        if request.auto_renew:
            subscription.renewal_failed = False
            subscription.renewal_attempts = 0
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Auto-renewal {'enabled' if request.auto_renew else 'disabled'}"
    }

# ✅ 6. GET PAYMENT METHODS
@router.get("/payment-methods/{email}")
def get_payment_methods(email: str, db: Session = Depends(get_db)):
    """Get user's saved payment methods"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.stripe_customer_id:
        return {"payment_methods": []}
    
    try:
        payment_methods = get_customer_payment_methods(user.stripe_customer_id)
        
        formatted_methods = []
        for pm in payment_methods:
            formatted_methods.append({
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
                "is_default": pm.id == user.default_payment_method_id
            })
        
        return {"payment_methods": formatted_methods}
    except Exception as e:
        print(f"❌ Error fetching payment methods: {e}")
        return {"payment_methods": []}

# ✅ 7. CANCEL SUBSCRIPTION (Disable Auto-Renewal)
@router.post("/cancel")
def cancel_subscription(request: dict, db: Session = Depends(get_db)):
    """Cancel subscription (disable auto-renewal)"""
    email = request.get("email")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()
    
    if subscription:
        subscription.auto_renew = False
        user.auto_renew_enabled = False
        db.commit()
        
        return {
            "success": True, 
            "message": "Auto-renewal disabled. Your subscription will end on the expiry date."
        }
    
    return {"success": True, "message": "No active subscription found"}

# ✅ 8. CHECK PAYMENT STATUS
@router.get("/payment-status/{payment_intent_id}")
def check_payment_status(payment_intent_id: str):
    """Check payment status"""
    try:
        payment_details = get_payment_intent_details(payment_intent_id)
        if not payment_details:
            raise HTTPException(status_code=404, detail="Payment intent not found")
        
        return {
            "payment_intent_id": payment_details["id"],
            "status": payment_details["status"],
            "amount": payment_details["amount"],
            "metadata": payment_details.get("metadata", {})
        }
    except Exception as e:
        print(f"❌ Payment status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))