# app/seed/subscription_seed.py - Updated for one-time payments

from sqlalchemy.orm import Session
from app.models.subscription import SubscriptionPlan
from app.db.database import SessionLocal

def seed_subscription_plans():
    db: Session = SessionLocal()

    # ✅ Updated plans with direct pricing (no Stripe price IDs)
    default_plans = [
        {
            "name": "Free",
            "description": "Basic free plan with limited usage",
            "monthly_price": 0,  # Free
            "yearly_price": 0,   # Free
            "query_limit": 10,
            "document_upload_limit": 0,
            "ninja_mode": False,
            "meme_generator": False
        },
        {
            "name": "Solo",
            "description": "Perfect for individual users",
            "monthly_price": 999,   # $9.99/month in cents
            "yearly_price": 9900,   # $99/year in cents (2 months free)
            "query_limit": 500,
            "document_upload_limit": 10,
            "ninja_mode": True,
            "meme_generator": True
        },
        {
            "name": "Team",
            "description": "For teams and businesses",
            "monthly_price": 2999,  # $29.99/month in cents
            "yearly_price": 29900,  # $299/year in cents (2 months free)
            "query_limit": 2000,
            "document_upload_limit": 50,
            "ninja_mode": True,
            "meme_generator": True
        },
        {
            "name": "Enterprise",
            "description": "For large organizations",
            "monthly_price": 9999,  # $99.99/month in cents
            "yearly_price": 99900,  # $999/year in cents (2 months free)
            "query_limit": 0,  # Unlimited
            "document_upload_limit": 200,
            "ninja_mode": True,
            "meme_generator": True
        }
    ]

    for plan_data in default_plans:
        existing = db.query(SubscriptionPlan).filter_by(name=plan_data["name"]).first()
        if not existing:
            plan = SubscriptionPlan(**plan_data)
            db.add(plan)
            print(f"✔ Plan added: {plan.name} - Monthly: ${plan.monthly_price/100:.2f}, Yearly: ${plan.yearly_price/100:.2f}")
        else:
            # Update existing plan with new pricing structure
            existing.monthly_price = plan_data["monthly_price"]
            existing.yearly_price = plan_data["yearly_price"]
            existing.query_limit = plan_data["query_limit"]
            existing.document_upload_limit = plan_data["document_upload_limit"]
            existing.ninja_mode = plan_data["ninja_mode"]
            existing.meme_generator = plan_data["meme_generator"]
            print(f"✔ Plan updated: {existing.name}")

    db.commit()
    db.close()
    print("✅ Subscription plans seeded successfully!")

if __name__ == "__main__":
    seed_subscription_plans()