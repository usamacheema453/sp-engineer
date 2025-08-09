from pydantic import BaseModel, EmailStr, validator
from typing import Optional

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    is_2fa_enabled: Optional[bool] = False
    auth_method: Optional[str] = None  # 'email' or 'phone'
    phone_number: Optional[str] = None
    terms_accepted: bool

    @validator('terms_accepted')
    def validate_terms_acceptance(cls, v):
        if not v:
            raise ValueError('You must accept the terms and conditions to register')
        return v

class ShowUser(BaseModel):
    id: int
    email: EmailStr
    is_verified: bool

    class Config:
        from_attributes = True
