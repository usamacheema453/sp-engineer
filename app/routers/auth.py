from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.hash import bcrypt

from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo
from app.schemas.user import UserCreate, ShowUser

from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.utils.firebase_otp import verify_firebase_token, send_firebase_otp
from app.utils.token import confirm_email_token
from app.utils import email as email_utils

router = APIRouter()

# Signup
@router.post("/signup", response_model=ShowUser)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = bcrypt.hash(user.password)

    db_user = User(
        full_name=user.full_name,
        email=user.email,
        password=hashed_password,
        is_2fa_enabled=user.is_2fa_enabled,
        auth_method=user.auth_method,
        phone_number=user.phone_number
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Send email verification
    email_utils.send_verification_email(user.email)

    # Send Firebase OTP if 2FA is on and method is phone
    if user.is_2fa_enabled and user.auth_method == "phone":
        send_firebase_otp(user.phone_number)

    return db_user

# Email verification
@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    email = confirm_email_token(token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.commit()
    return {"message": "Email verified successfully"}

# Login
@router.post("/login", response_model=LoginResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not bcrypt.verify(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")
    
    if user.is_2fa_enabled:
        if not payload.otp_token:
            raise HTTPException(status_code=403, detail="2FA is enabled. OTP token is required.")
        if not verify_firebase_token(payload.otp_token):
            raise HTTPException(status_code=403, detail="Invalid OTP token")

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }
