from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, ShowUser
from app.utils import email as email_utils
from app.utils.token import confirm_email_token
from app.utils.firebase import send_firebase_otp
from app.db.database import get_db
from passlib.hash import bcrypt

router = APIRouter(prefix="/auth", tags=["Auth"])

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

    email_utils.send_verification_email(user.email)

    if user.is_2fa_enabled and user.auth_method == "phone":
        send_firebase_otp(user.phone_number)

    return db_user

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
