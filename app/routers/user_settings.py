from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.user_settings import UserSettings
from passlib.hash import bcrypt

router = APIRouter(prefix="/user-settings", tags=["User Settings"])

# ✅ UPDATED SCHEMAS
from pydantic import BaseModel

class NotificationSettingsRequest(BaseModel):
    email_notifications: bool
    push_notifications: bool
    marketing_communications: bool

class PersonalizationSettingsRequest(BaseModel):
    profile_avatar: Optional[str] = None
    profession: Optional[str] = None
    industry: Optional[str] = None
    expertise_level: Optional[str] = None
    communication_tone: Optional[str] = None
    response_instructions: Optional[str] = None
    nickname: Optional[str] = None  # ✅ NEW: Added nickname

class Toggle2FARequest(BaseModel):
    is_2fa_enabled: bool

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# ✅ NEW: General settings update request
class GeneralSettingsRequest(BaseModel):
    phone_number: Optional[str] = None

# ✅ UPDATED: Main response with user data
class AllUserSettingsResponse(BaseModel):
    # ✅ NEW: User basic info
    full_name: str
    email: str
    phone_number: Optional[str]
    nickname: Optional[str]
    
    # Notifications
    email_notifications: bool
    push_notifications: bool
    marketing_communications: bool
    
    # Personalization
    profile_avatar: Optional[str]
    profession: Optional[str]
    industry: Optional[str]
    expertise_level: str
    communication_tone: str
    response_instructions: Optional[str]
    
    # Security (from main User table)
    is_2fa_enabled: bool
    
    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ✅ HELPER FUNCTIONS
def get_or_create_user_settings(db: Session, user_id: int) -> UserSettings:
    """Get user settings, create if doesn't exist"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    if not settings:
        print(f"Creating default settings for user {user_id}")
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
        print(f"✅ Default settings created for user {user_id}")
    
    return settings

# ✅ MAIN ENDPOINTS

# ✅ IMPORTANT: Specific routes MUST come before generic "/" route to avoid conflicts

# ✅ NEW: General settings endpoints (MOVED UP)
@router.get("/general")
def get_general_settings(
    current_user: User = Depends(get_current_user)
):
    """Get general user settings (phone, name, email)"""
    try:
        return {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "nickname": current_user.nickname,
            "message": "General settings retrieved successfully!"
        }
    except Exception as e:
        print(f"❌ Error getting general settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get general settings: {str(e)}"
        )

@router.put("/general")
def update_general_settings(
    data: GeneralSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update general settings (phone number)"""
    try:
        print(f"Updating general settings for user {current_user.id}: {data}")
        
        # Update phone number if provided
        if data.phone_number is not None:
            current_user.phone_number = data.phone_number
        
        db.commit()
        db.refresh(current_user)
        
        print(f"✅ General settings updated for user {current_user.id}")
        
        return {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "nickname": current_user.nickname,
            "message": "General settings updated successfully!"
        }
    except Exception as e:
        print(f"❌ Error updating general settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update general settings: {str(e)}"
        )

@router.get("/notifications")
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications
        }
    except Exception as e:
        print(f"❌ Error getting notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification settings: {str(e)}"
        )

@router.get("/personalization")
def get_personalization_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalization settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname  # ✅ NEW: Added nickname from User table
        }
    except Exception as e:
        print(f"❌ Error getting personalization settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personalization settings: {str(e)}"
        )

@router.get("/security")
def get_security_settings(
    current_user: User = Depends(get_current_user)
):
    """Get security settings"""
    try:
        return {
            "is_2fa_enabled": current_user.is_2fa_enabled,
            "message": "Security settings retrieved successfully!"
        }
    except Exception as e:
        print(f"❌ Error getting security settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )

# ✅ Main endpoint - MUST be at the end to avoid route conflicts
@router.get("/", response_model=AllUserSettingsResponse)
def get_all_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all user settings including user basic info"""
    try:
        print(f"Getting settings for user {current_user.id}")
        
        # Get or create settings
        settings = get_or_create_user_settings(db, current_user.id)
        
        # ✅ UPDATED: Build response with user data
        response_data = {
            # ✅ NEW: User basic information
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "nickname": current_user.nickname,
            
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
            
            # Security settings (from main User table)
            "is_2fa_enabled": current_user.is_2fa_enabled,
            
            # Metadata
            "created_at": settings.created_at,
            "updated_at": settings.updated_at
        }
        
        print(f"✅ Settings retrieved for user {current_user.id}")
        return AllUserSettingsResponse(**response_data)
        
    except Exception as e:
        print(f"❌ Error getting settings for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve settings: {str(e)}"
        )

@router.get("/notifications")
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications
        }
    except Exception as e:
        print(f"❌ Error getting notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification settings: {str(e)}"
        )

@router.put("/notifications")
def update_notification_settings(
    data: NotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification settings"""
    try:
        print(f"Updating notification settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update notification settings
        settings.email_notifications = data.email_notifications
        settings.push_notifications = data.push_notifications
        settings.marketing_communications = data.marketing_communications
        settings.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(settings)
        
        print(f"✅ Notification settings updated for user {current_user.id}")
        
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications,
            "message": "Notification settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating notification settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )

@router.get("/personalization")
def get_personalization_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalization settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname  # ✅ NEW: Added nickname from User table
        }
    except Exception as e:
        print(f"❌ Error getting personalization settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personalization settings: {str(e)}"
        )

@router.put("/personalization")
def update_personalization_settings(
    data: PersonalizationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update personalization settings including nickname"""
    try:
        print(f"Updating personalization settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update UserSettings table fields
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
        
        # ✅ NEW: Update nickname in User table
        if data.nickname is not None:
            current_user.nickname = data.nickname
        
        db.commit()
        db.refresh(settings)
        db.refresh(current_user)
        
        print(f"✅ Personalization settings updated for user {current_user.id}")
        
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname,  # ✅ NEW: Return updated nickname
            "message": "Personalization settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating personalization settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personalization settings: {str(e)}"
        )

# ✅ UPDATE endpoints for specific sections
@router.put("/notifications")
def update_notification_settings(
    data: NotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification settings"""
    try:
        print(f"Updating notification settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update notification settings
        settings.email_notifications = data.email_notifications
        settings.push_notifications = data.push_notifications
        settings.marketing_communications = data.marketing_communications
        settings.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(settings)
        
        print(f"✅ Notification settings updated for user {current_user.id}")
        
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications,
            "message": "Notification settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating notification settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )

@router.put("/personalization")
def update_personalization_settings(
    data: PersonalizationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update personalization settings including nickname"""
    try:
        print(f"Updating personalization settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update UserSettings table fields
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
        
        # ✅ NEW: Update nickname in User table
        if data.nickname is not None:
            current_user.nickname = data.nickname
        
        db.commit()
        db.refresh(settings)
        db.refresh(current_user)
        
        print(f"✅ Personalization settings updated for user {current_user.id}")
        
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname,  # ✅ NEW: Return updated nickname
            "message": "Personalization settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating personalization settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personalization settings: {str(e)}"
        )
def get_security_settings(
    current_user: User = Depends(get_current_user)
):
    """Get security settings"""
    try:
        return {
            "is_2fa_enabled": current_user.is_2fa_enabled,
            "message": "Security settings retrieved successfully!"
        }
    except Exception as e:
        print(f"❌ Error getting security settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )

@router.put("/security/2fa")
def toggle_2fa(
    data: Toggle2FARequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle 2FA on/off"""
    try:
        print(f"Toggling 2FA for user {current_user.id}: {data.is_2fa_enabled}")
        
        current_user.is_2fa_enabled = data.is_2fa_enabled
        db.commit()
        
        status_text = "enabled" if data.is_2fa_enabled else "disabled"
        print(f"✅ 2FA {status_text} for user {current_user.id}")
        
        return {
            "is_2fa_enabled": current_user.is_2fa_enabled,
            "message": f"2FA successfully {status_text}!"
        }
    except Exception as e:
        print(f"❌ Error toggling 2FA: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update 2FA settings: {str(e)}"
        )

@router.post("/security/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        # Verify current password
        if not bcrypt.verify(data.current_password, current_user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect!"
            )
        
        # Hash and update new password
        hashed_password = bcrypt.hash(data.new_password)
        current_user.password = hashed_password
        db.commit()
        
        print(f"✅ Password changed for user {current_user.id}")
        
        return {
            "message": "Password changed successfully!",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error changing password: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )

# ✅ DEBUG ENDPOINTS (Remove in production)
@router.get("/debug/test")
def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "status": "ok",
        "message": "User Settings API is working!",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/debug/auth-test")
def test_auth_endpoint(current_user: User = Depends(get_current_user)):
    """Test authentication"""
    return {
        "status": "authenticated",
        "user_id": current_user.id,
        "user_email": current_user.email,
        "user_full_name": current_user.full_name,  # ✅ NEW: Added for debugging
        "user_phone": current_user.phone_number,   # ✅ NEW: Added for debugging
        "user_nickname": current_user.nickname,    # ✅ NEW: Added for debugging
        "message": "Authentication working!"
    }