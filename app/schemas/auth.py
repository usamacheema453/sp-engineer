# app/schemas/auth.py

from pydantic import BaseModel, EmailStr
from typing import Optional

# Input schema for login
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp_token: Optional[str] = None  # Only needed if 2FA is enabled


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
    access_token: str
    refresh_token: str
    token_type: str
    user: UserInfo
