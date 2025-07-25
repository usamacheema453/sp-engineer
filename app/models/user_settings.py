
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime

class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Notification settings
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    marketing_communications = Column(Boolean, default=False)
    
    # Personalization settings
    profile_avatar = Column(String, nullable=True)
    profession = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    expertise_level = Column(String, default="intermediate")
    communication_tone = Column(String, default="casual_friendly")
    response_instructions = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="settings")
