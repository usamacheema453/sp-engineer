from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    is_2fa_enabled: Optional[bool] = False
    auth_method: Optional[str] = None  # 'email' or 'phone'
    phone_number: Optional[str] = None

class ShowUser(BaseModel):
    id: int
    email: EmailStr
    is_verified: bool

    class Config:
        from_attributes = True
