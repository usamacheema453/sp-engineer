
from sqlalchemy.orm import Session
from app.models.user_settings import UserSettings
from app.models.user import User
from app.schemas.user_settings import (
    NotificationSettingsRequest,
    PersonalizationSettingsRequest
)
from datetime import datetime

def get_or_create_user_settings(db: Session, user_id: int) -> UserSettings:
    """User settings get karo ya create karo agar nahi hai"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    if not settings:
        # Default settings create karo
        settings = UserSettings(
            user_id=user_id,
            email_notifications=True,
            push_notifications=True,
            marketing_communications=False,
            expertise_level="intermediate",
            communication_tone="casual_friendly"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings

def update_notification_settings(
    db: Session, 
    user_id: int, 
    data: NotificationSettingsRequest
) -> UserSettings:
    """Notification settings update karo"""
    settings = get_or_create_user_settings(db, user_id)
    
    # Frontend se jo data aaya usse update karo
    settings.email_notifications = data.email_notifications
    settings.push_notifications = data.push_notifications
    settings.marketing_communications = data.marketing_communications
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(settings)
    return settings

def update_personalization_settings(
    db: Session, 
    user_id: int, 
    data: PersonalizationSettingsRequest
) -> UserSettings:
    """Personalization settings update karo"""
    settings = get_or_create_user_settings(db, user_id)
    
    # Frontend se jo data aaya usse update karo (sirf jo fields bheje gaye hain)
    if data.profile_avatar is not None:
        settings.profile_avatar = data.profile_avatar
    if data.profession is not None:
        settings.profession = data.profession
    if data.industry is not None:
        settings.industry = data.industry
    if data.expertise_level is not None:
        settings.expertise_level = data.expertise_level
    if data.communication_tone is not None:
        settings.communication_tone = data.communication_tone
    if data.response_instructions is not None:
        settings.response_instructions = data.response_instructions
    
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(settings)
    return settings

def get_all_user_settings(db: Session, user_id: int) -> dict:
    """Saari settings ek saath get karo"""
    settings = get_or_create_user_settings(db, user_id)
    user = db.query(User).filter(User.id == user_id).first()
    
    return {
        # Notification settings
        "email_notifications": settings.email_notifications,
        "push_notifications": settings.push_notifications,
        "marketing_communications": settings.marketing_communications,
        
        # Personalization settings
        "profile_avatar": settings.profile_avatar,
        "profession": settings.profession,
        "industry": settings.industry,
        "expertise_level": settings.expertise_level,
        "communication_tone": settings.communication_tone,
        "response_instructions": settings.response_instructions,
        
        # Security settings (main table se)
        "is_2fa_enabled": user.is_2fa_enabled if user else False,
        
        # Metadata
        "created_at": settings.created_at,
        "updated_at": settings.updated_at
    }
