from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db
from app.models.subscription import UserSubscription
from app.models.user import User

def check_subscription_usage(
    user: User,
    db: Session = Depends(get_db),
    check_query: bool = False,
    check_document: bool = False
):
    subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=403, 
            detail="No active subscription found. Please select a subscription plan to access this feature.",
            headers={
                "X-Requires-Subscription": "true",
                "X-Plans-Endpoint": "/subscriptions/plans"
            }
        )

    if subscription.expiry_date < datetime.utcnow():
        subscription.active = False
        db.commit()
        raise HTTPException(
            status_code=403, 
            detail="Subscription expired. Please renew your plan.",
            headers={"X-Subscription-Expired": "true"}
        )

    plan = subscription.plan

    if check_query and subscription.queries_used >= plan.query_limit:
        raise HTTPException(
            status_code=403, 
            detail=f"Query limit exceeded. You have used {subscription.queries_used}/{plan.query_limit} queries."
        )

    if check_document and subscription.documents_uploaded >= plan.document_upload_limit:
        raise HTTPException(
            status_code=403, 
            detail=f"Document upload limit exceeded. You have uploaded {subscription.documents_uploaded}/{plan.document_upload_limit} documents."
        )

    return subscription

# ✅ OPTIONAL: Add endpoint to check if user needs to select plan

@router.get("/needs-plan-selection/{email}")
def needs_plan_selection(email: str, db: Session = Depends(get_db)):
    """Check if user needs to select a subscription plan"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    has_active_subscription = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.active == True
    ).first() is not None
    
    return {
        "needs_plan_selection": not has_active_subscription,
        "has_active_subscription": has_active_subscription,
        "user_email": email
    }