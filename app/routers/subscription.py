from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription
from app.schemas.subscription import SubscriptionStartRequest, SubscriptionStartResponse
from app.utils.stripe_service import create_customer, create_subscription
from datetime import datetime, timedelta

router = APIRouter(prefix="/subscriptions", tags=["Subscription"])

@router.post("/start", response_model=SubscriptionStartResponse)
def start_subscription(req: SubscriptionStartRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(404, "User not found")

    if not user.stripe_customer_id:
        cid = create_customer(user.email)
        user.stripe_customer_id = cid
        db.commit()

    # stripe price ID is sent from frontend via req.price_id
    sub_data = create_subscription(user.stripe_customer_id, req.price_id)

    return SubscriptionStartResponse(
        subscription_id=sub_data["subscription_id"],
        client_secret=sub_data["client_secret"]
    )
