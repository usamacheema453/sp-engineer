from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from datetime import datetime, timedelta
from typing import List, Dict
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.schemas.subscription import SubscriptionStartRequest, SubscriptionStartResponse
from app.utils.stripe_service import create_customer, create_subscription
from app.utils.stripe_service import create_customer
import stripe
from app.config import STRIPE_SECRET_KEY
from pydantic import BaseModel

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Your existing router
router = APIRouter(prefix="/subscriptions", tags=["Subscription"])

# ✅ Add this missing schema for checkout request
class CheckoutSessionRequest(BaseModel):
    email: str
    plan_id: str
    billing_cycle: str
    success_url: str
    cancel_url: str

# ✅ ADD THE MISSING ENDPOINT
# app/routers/subscription.py mein add karein

@router.post("/create-checkout-session")
def create_checkout_session(request: dict, db: Session = Depends(get_db)):
    try:
        email = request.get("email")
        plan_id = request.get("plan_id")
        billing_cycle = request.get("billing_cycle", "monthly")
        success_url = request.get("success_url")
        cancel_url = request.get("cancel_url")
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # ✅ Fix: Check if customer ID is mock, create real one
        if not user.stripe_customer_id or user.stripe_customer_id.startswith('cus_mock_'):
            # Create real Stripe customer
            real_customer_id = create_customer(email)
            user.stripe_customer_id = real_customer_id
            db.commit()
        
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Get correct price ID
        price_id = plan.stripe_yearly_price_id if billing_cycle == "yearly" else plan.stripe_monthly_price_id
        
        if not price_id:
            raise HTTPException(status_code=400, detail="Price ID not configured for this plan")
        
        # Create Stripe checkout session
        import stripe
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
        )
        
        return {"checkout_url": checkout_session.url}
        
    except Exception as e:
        print(f"❌ Checkout session error: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

@router.get("/plans")
def get_subscription_plans(db: Session = Depends(get_db)):
    plans = db.query(SubscriptionPlan).all()
    
    formatted_plans = []
    for plan in plans:
        formatted_plans.append({
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "price": plan.price,  # Price in cents
            "query_limit": plan.query_limit,
            "document_upload_limit": plan.document_upload_limit,
            "ninja_mode": plan.ninja_mode,
            "meme_generator": plan.meme_generator,
            "features": {
                "queries": f"{plan.query_limit} queries/month" if plan.query_limit > 0 else "Unlimited queries",
                "users": "1 user account",
                "ninja_mode": plan.ninja_mode,
                "meme_generator": plan.meme_generator
            },
            "stripe_monthly_price_id": plan.stripe_monthly_price_id,
            "stripe_yearly_price_id": plan.stripe_yearly_price_id
        })
    
    return {"plans": formatted_plans}


@router.get("/current/{email}")
def get_current_subscription(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()
    
    if subscription:
        plan_name = subscription.plan.name.lower()
    else:
        plan_name = "free"
    
    return {"plan": plan_name}


@router.post("/confirm-payment")
def confirm_payment(request: dict, db: Session = Depends(get_db)):
    subscription_id = request.get("subscription_id")
    payment_intent_id = request.get("payment_intent_id")
    
    # Here you would verify the payment with Stripe
    # For now, we'll assume it's successful
    
    return {"success": True, "message": "Payment confirmed"}


@router.post("/cancel")
def cancel_subscription(request: dict, db: Session = Depends(get_db)):
    email = request.get("email")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cancel active subscription
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()
    
    if subscription:
        subscription.active = False
        db.commit()
    
    return {"success": True, "message": "Subscription cancelled"}


@router.post("/activate")
def activate_subscription(request: dict, db: Session = Depends(get_db)):
    user_email = request.get("user_email")
    plan_name = request.get("plan_name")
    billing_cycle = request.get("billing_cycle", "monthly")
    
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name.ilike(plan_name)).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # ✅ Cancel any existing active subscriptions first
    existing_subscriptions = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).all()
    
    for sub in existing_subscriptions:
        sub.active = False
    
    # ✅ Create or update subscription
    new_subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        active=True,
        billing_cycle=billing_cycle,
        start_date=datetime.utcnow(),
        expiry_date=datetime.utcnow() + timedelta(days=30 if billing_cycle == "monthly" else 365),
        queries_used=0,  # ✅ Reset usage
        documents_uploaded=0  # ✅ Reset usage
    )
    db.add(new_subscription)
    
    db.commit()
    
    return {"success": True, "message": f"{plan_name} plan activated successfully"}