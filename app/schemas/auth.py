# app/schemas/auth.py - Updated with first-time login fields

from pydantic import BaseModel, EmailStr
from typing import Optional

# Input schema for login
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class UserInfo(BaseModel):
    id: int
    full_name: str
    email: str
    is_2fa_enabled: Optional[bool]
    auth_method: Optional[str]
    phone_number: Optional[str]
    # ✅ NEW: First-time login tracking fields
    login_count: Optional[int] = 0
    first_login_completed: Optional[bool] = False

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    requires_2fa: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[UserInfo] = None
    auth_method: Optional[str] = None
    contact: Optional[str] = None
    message: Optional[str] = None
    # ✅ NEW: First-time login indicator
    is_first_login: Optional[bool] = False
    login_count: Optional[int] = 0

class CompleteLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserInfo
    # ✅ NEW: First-time login indicator
    is_first_login: bool = False
    login_count: int = 0

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class Send2FAOTPRequest(BaseModel):
    email: EmailStr
    auth_method: str  # "email" or "phone"
    contact: str  # email address or phone number

class Verify2FAOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str
    auth_method: str