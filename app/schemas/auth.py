# app/schemas/auth.py

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

    class Config:
        from_attribue = True

class LoginResponse(BaseModel):
    requires_2fa: bool
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[UserInfo] = None
    auth_method: Optional[str] = None
    contact: Optional[str] = None
    message: Optional[str] = None

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

class CompleteLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserInfo

class Verify2FAOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str
    auth_method: str