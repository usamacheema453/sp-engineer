from datetime import datetime
from app.db.database import SessionLocal
from app.models.subscription import UserSubscription
from app.models.user import User
from app.utils.email import send_email

db = SessionLocal()

subs = db.query(UserSubscription).filter(UserSubscription.expire_date <= datetime.utcnow(), UserSubscription.is_active == True).all()

for sub in subs:
    sub.is_active = False
    db.commit()

    user = db.query(User).filter(User.id == sub.user_id).first()
    if user:
        send_email(
            to=user.email,
            subject="Subscription Expired",
            body="Your subscription has expired. Please renew to continue using the service."
        )

print("Expired subscriptions handled.")
