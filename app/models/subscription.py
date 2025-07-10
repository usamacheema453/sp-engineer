# Update your app/models/subscription.py - add these columns to SubscriptionPlan:

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
from datetime import datetime

class BillingCycle(enum.Enum):
    monthly = "monthly"
    yearly = "yearly"

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Integer, nullable=True)
    query_limit = Column(Integer, default=0)
    document_upload_limit = Column(Integer, default=0)
    ninja_mode = Column(Boolean, default=False)
    meme_generator = Column(Boolean, default=False)
    
    # ✅ Add these new columns for Stripe
    stripe_monthly_price_id = Column(String, nullable=True)
    stripe_yearly_price_id = Column(String, nullable=True)

    # ✅ Relationship to UserSubscription
    subscriptions = relationship("UserSubscription", back_populates="plan")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)

    start_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=False)

    billing_cycle = Column(Enum(BillingCycle), default=BillingCycle.monthly)
    active = Column(Boolean, default=True)
    auto_renew = Column(Boolean, default=True)

    # ✅ Track usage
    queries_used = Column(Integer, default=0)
    documents_uploaded = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")