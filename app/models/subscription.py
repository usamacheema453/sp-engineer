# app/models/subscription.py - Updated for one-time payments

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum
from datetime import datetime

class BillingCycle(enum.Enum):
    monthly = "monthly"
    yearly = "yearly"

class CancellationReason(enum.Enum):
    user_request = "user_request"
    payment_failed = "payment_failed"
    admin_action = "admin_action"
    other = "other"

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    
    # Pricing in cents (USD)
    monthly_price = Column(Integer, nullable=True)  # Price in cents for monthly
    yearly_price = Column(Integer, nullable=True)   # Price in cents for yearly
    
    query_limit = Column(Integer, default=0)
    document_upload_limit = Column(Integer, default=0)
    ninja_mode = Column(Boolean, default=False)
    meme_generator = Column(Boolean, default=False)
    
    # Remove Stripe price IDs since we're using one-time payments
    # stripe_monthly_price_id = Column(String, nullable=True)  # Remove
    # stripe_yearly_price_id = Column(String, nullable=True)   # Remove

    # ✅ Relationship to UserSubscription
    subscriptions = relationship("UserSubscription", back_populates="plan")

class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)

    start_date = Column(DateTime, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=False)
    
    billing_cycle = Column(Enum(BillingCycle, name="billingcycle", create_type=False), default=BillingCycle.monthly)


    active = Column(Boolean, default=True)
    
    # Auto-renewal preferences
    auto_renew = Column(Boolean, default=True)

    # ✅ NEW: Cancellation fields
    is_cancelled = Column(Boolean, default=False)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Enum(CancellationReason, name="cancellationreason", create_type=False), nullable=True)
    cancellation_note = Column(Text, nullable=True)
    cancelled_by_user_id = Column(Integer, nullable=True)  # Who cancelled it

        # ✅ Access period tracking
    access_ends_at = Column(DateTime, nullable=True)  # When user loses access (same as expiry for cancelled subs)
    
    # Payment tracking for one-time payments
    last_payment_date = Column(DateTime, nullable=True)
    last_payment_intent_id = Column(String, nullable=True)  # Stripe PaymentIntent ID
    payment_method_id = Column(String, nullable=True)  # Stored payment method
    
    # ✅ NEW: Renewal tracking
    next_renewal_date = Column(DateTime, nullable=True)
    renewal_attempts = Column(Integer, default=0)
    last_renewal_attempt = Column(DateTime, nullable=True)
    renewal_failed = Column(Boolean, default=False)
    failure_reason = Column(Text, nullable=True)

    # ✅ Track usage
    queries_used = Column(Integer, default=0)
    documents_uploaded = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="subscription")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

# ✅ NEW: Payment History Model
class PaymentHistory(Base):
    __tablename__ = "payment_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id"), nullable=False)
    
    payment_intent_id = Column(String, nullable=False)  # Stripe PaymentIntent ID
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String, default="usd")
    status = Column(String, nullable=False)  # succeeded, failed, etc.
    
    billing_cycle = Column(Enum(BillingCycle), nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    is_renewal = Column(Boolean, default=False)
    meta_info = Column(Text, nullable=True)  # JSON string for additional data
    
    # Relationships
    user = relationship("User")
    subscription = relationship("UserSubscription")

# ✅ NEW: Cancellation History Model
class SubscriptionCancellation(Base):
    __tablename__ = "subscription_cancellations"
    
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("user_subscriptions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    cancelled_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(Enum(CancellationReason), nullable=False)
    user_feedback = Column(Text, nullable=True)  # User's reason for cancelling
    
    # Subscription details at time of cancellation
    plan_name = Column(String, nullable=False)
    billing_cycle = Column(String, nullable=False)
    remaining_days = Column(Integer, nullable=True)
    access_until = Column(DateTime, nullable=False)
    
    # Financial details
    prorated_refund_amount = Column(Integer, default=0)  # In cents
    refund_processed = Column(Boolean, default=False)
    refund_transaction_id = Column(String, nullable=True)
    
    # Metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User")
    subscription = relationship("UserSubscription")