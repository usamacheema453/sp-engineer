from sqlalchemy.orm import Session
from app.models.subscription import SubscriptionPlan
from app.db.database import SessionLocal


def seed_subscription_plans():
    db: Session = SessionLocal()

    default_plans = [
        {
            "name": "Free",
            "description": "Basic free plan with limited usage",
            "price": 0,
            "query_limit": 10,
            "document_upload_limit": 0,
            "ninja_mode": False,
            "meme_generator": False
        },
        {
            "name": "Solo",
            "description": "Solo plan with extended features",
            "price": None,  # Will be set from frontend
            "query_limit": 250,
            "document_upload_limit": 3,
            "ninja_mode": True,
            "meme_generator": True
        }
    ]

    for plan_data in default_plans:
        existing = db.query(SubscriptionPlan).filter_by(name=plan_data["name"]).first()
        if not existing:
            plan = SubscriptionPlan(**plan_data)
            db.add(plan)
            print(f"✔ Plan added: {plan.name}")

    db.commit()
    db.close()
