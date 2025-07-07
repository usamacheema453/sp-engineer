# app/models/user.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.database import Base
from sqlalchemy.orm import relationship

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
    stripe_customer_id = Column(String, nullable=True)
    subscription = relationship("UserSubscription", back_populates="user", uselist=False)
    reset_token = Column(String, nullable=True)
    last_login = Column(DateTime, nullable=True)