# app/dependencies/subscription_check.py

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
        UserSubscription.is_active == True
    ).first()

    if not subscription:
        raise HTTPException(status_code=403, detail="No active subscription")

    if subscription.end_date < datetime.utcnow():
        subscription.is_active = False
        db.commit()
        raise HTTPException(status_code=403, detail="Subscription expired")

    plan = subscription.plan

    if check_query and subscription.queries_used >= plan.query_limit:
        raise HTTPException(status_code=403, detail="Query limit exceeded")

    if check_document and subscription.documents_uploaded >= plan.max_documents:
        raise HTTPException(status_code=403, detail="Document upload limit exceeded")

    return subscription
