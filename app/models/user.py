# app/models/user.py

from sqlalchemy import Column, Integer, String, Boolean
from app.db.database import Base

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
