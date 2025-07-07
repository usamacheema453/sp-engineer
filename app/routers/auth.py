from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from fastapi.security import OAuth2PasswordBearer

from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserCreate, ShowUser
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest

from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.utils.firebase_otp import verify_firebase_token, send_firebase_otp
from app.utils.token import confirm_email_token, generate_reset_token, confirm_reset_token
from app.utils.email import (
    send_verification_email,
    send_password_reset_email,
    generate_otp,
    send_email_otp,
    store_otp,
    verify_email_otp,
)

router = APIRouter()


# ------------------ SIGNUP ------------------
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
    send_verification_email(user.email)

    # Send OTP based on selected 2FA method
    if user.is_2fa_enabled:
        if user.auth_method == "phone":
            send_firebase_otp(user.phone_number)
        elif user.auth_method == "email":
            otp = generate_otp()
            store_otp(user.email, otp)
            send_email_otp(user.email, otp)

    return db_user


# ------------------ EMAIL VERIFICATION ------------------
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


# ------------------ LOGIN ------------------
@router.post("/login", response_model=LoginResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not bcrypt.verify(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

    # Handle 2FA based on selected method
    if user.is_2fa_enabled:
        if not payload.otp_token:
            raise HTTPException(status_code=403, detail="2FA is enabled. OTP token is required.")

        if user.auth_method == "phone":
            if not verify_firebase_token(payload.otp_token):
                raise HTTPException(status_code=403, detail="Invalid phone OTP token.")
        elif user.auth_method == "email":
            if not verify_email_otp(user.email, payload.otp_token):
                raise HTTPException(status_code=403, detail="Invalid or expired email OTP.")

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }


# ------------------ FORGOT PASSWORD ------------------
@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = generate_reset_token(user.email)
    user.reset_token = token
    db.commit()

    send_password_reset_email(user.email, token)
    return {"message": "Password reset link sent to your email."}


# ------------------ RESET PASSWORD ------------------
@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = confirm_reset_token(request.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")

    user = db.query(User).filter(User.email == email).first()
    if not user or user.reset_token != request.token:
        raise HTTPException(status_code=400, detail="Invalid token.")

    user.password = bcrypt.hash(request.new_password)
    user.reset_token = None
    db.commit()

    return {"message": "Password reset successful."}


# ------------------ LOGOUT ------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/logout")
def logout_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    blacklist_token(token, db)  # Assuming this function exists
    return {"message": "Successfully logged out."}
