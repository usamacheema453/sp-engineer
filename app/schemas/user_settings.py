
from pydantic import BaseModel, validator
from typing import Optional
from datetime import datetime

# ✅ NOTIFICATION SETTINGS REQUEST/RESPONSE
class NotificationSettingsRequest(BaseModel):
    email_notifications: bool
    push_notifications: bool
    marketing_communications: bool

class NotificationSettingsResponse(BaseModel):
    email_notifications: bool
    push_notifications: bool
    marketing_communications: bool
    message: str = "Notification settings updated successfully"

# ✅ PERSONALIZATION SETTINGS REQUEST/RESPONSE
class PersonalizationSettingsRequest(BaseModel):
    profile_avatar: Optional[str] = None
    profession: Optional[str] = None
    industry: Optional[str] = None
    expertise_level: Optional[str] = None  # Frontend se jo enable ho uska name
    communication_tone: Optional[str] = None  # Frontend se jo enable ho uska name
    response_instructions: Optional[str] = None

class PersonalizationSettingsResponse(BaseModel):
    profile_avatar: Optional[str]
    profession: Optional[str]
    industry: Optional[str]
    expertise_level: str
    communication_tone: str
    response_instructions: Optional[str]
    message: str = "Personalization settings updated successfully"

# ✅ SECURITY SETTINGS REQUEST/RESPONSE
class SecuritySettingsResponse(BaseModel):
    is_2fa_enabled: bool
    message: str = "Security settings retrieved successfully"

class Toggle2FARequest(BaseModel):
    is_2fa_enabled: bool

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

# ✅ COMPLETE SETTINGS RESPONSE
class AllUserSettingsResponse(BaseModel):
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