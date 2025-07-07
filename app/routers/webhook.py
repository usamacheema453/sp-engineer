import stripe
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from app.config import STRIPE_WEBHOOK_SECRET
from app.db.database import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.subscription import UserSubscription
from app.utils.email import send_email

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
        raise HTTPException(status_code=400, detail=f"Webhook Error: {str(e)}")

    event_type = event['type']
    data = event['data']['object']

    if event_type == "invoice.payment_succeeded":
        customer_id = data['customer']
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            # Extend subscription by 30 days
            sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
            if sub:
                from datetime import datetime, timedelta
                sub.start_date = datetime.utcnow()
                sub.expire_date = datetime.utcnow() + timedelta(days=30)
                sub.is_active = True
                db.commit()

                send_email(
                    to=user.email,
                    subject="Subscription Renewed",
                    body="Your subscription was successfully renewed!"
                )

    elif event_type == "invoice.payment_failed":
        customer_id = data['customer']
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            send_email(
                to=user.email,
                subject="Payment Failed",
                body="We could not process your subscription renewal. Please check your payment method."
            )

    return {"status": "success"}
