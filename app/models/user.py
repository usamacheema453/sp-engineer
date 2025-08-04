# app/models/user.py - Updated for first-time login tracking

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.database import Base
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    is_2fa_enabled = Column(Boolean, default=False)
    auth_method = Column(String, nullable=True)  # "email" or "phone"
    phone_number = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    
    # Stripe customer info
    stripe_customer_id = Column(String, nullable=True)
    
    # NEW: Default payment method for renewals
    default_payment_method_id = Column(String, nullable=True)
    
    # NEW: Payment preferences
    auto_renew_enabled = Column(Boolean, default=True)  # Global auto-renew preference
    email_notifications = Column(Boolean, default=True)  # Email notifications for renewals
    
    # ✅ NEW: First-time login tracking
    first_login_completed = Column(Boolean, default=False)  # Track if user completed first login flow
    login_count = Column(Integer, default=0)  # Track total logins
    created_at = Column(DateTime, default=datetime.utcnow)  # Track account creation
    
    # Existing fields
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)
    reset_token = Column(String, nullable=True)
    last_login = Column(DateTime, nullable=True)
    settings = relationship("UserSettings", back_populates="user", uselist=False)
    firebase_uid = Column(String, nullable=True, unique=True) 