from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db  # <-- Add this line
from datetime import datetime, timedelta
from typing import List, Dict
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.schemas.subscription import SubscriptionStartRequest, SubscriptionStartResponse
from app.utils.stripe_service import create_customer, create_subscription

# Your existing router
router = APIRouter(prefix="/subscriptions", tags=["Subscription"])


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
            "stripe_monthly_price_id": f"price_{plan.name.lower()}_monthly",
            "stripe_yearly_price_id": f"price_{plan.name.lower()}_yearly"
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
    
    # Create or update subscription
    existing_subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id
    ).first()
    
    if existing_subscription:
        existing_subscription.plan_id = plan.id
        existing_subscription.active = True
        existing_subscription.billing_cycle = billing_cycle
        existing_subscription.start_date = datetime.utcnow()
        existing_subscription.expiry_date = datetime.utcnow() + timedelta(days=30 if billing_cycle == "monthly" else 365)
    else:
        new_subscription = UserSubscription(
            user_id=user.id,
            plan_id=plan.id,
            active=True,
            billing_cycle=billing_cycle,
            start_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=30 if billing_cycle == "monthly" else 365)
        )
        db.add(new_subscription)
    
    db.commit()
    
    return {"success": True, "message": "Subscription activated"}