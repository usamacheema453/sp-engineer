from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from fastapi.security import OAuth2PasswordBearer

from datetime import datetime
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo, Send2FAOTPRequest, Verify2FAOTPRequest
from app.schemas.user import UserCreate, ShowUser
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordRequest

from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.utils.firebase_otp import verify_firebase_token, send_firebase_otp
from app.utils.token import confirm_email_token, generate_reset_token, confirm_reset_token, blacklist_token
from app.utils.email import (
    send_verification_email,
    send_password_reset_email,
    generate_otp,
    send_email_otp,
    store_otp,
    verify_email_otp,
)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Helper function to update login tracking
def update_login_tracking(user: User, db: Session):
    """Update user login tracking"""
    current_time = datetime.utcnow()
    
    # Update login count and last login
    user.login_count += 1
    user.last_login = current_time
    
    # Check if this is first time completing login flow
    is_first_login = not user.first_login_completed
    
    # Mark first login as completed
    if not user.first_login_completed:
        user.first_login_completed = True
    
    db.commit()
    
    return is_first_login

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

    # ✅ ONLY send email verification during signup
    send_verification_email(user.email)

    # ❌ DO NOT send OTP here - it will be sent later via /send-2fa-otp endpoint
    # Remove any OTP sending code from here

    return db_user



# Add after your existing signup endpoint
@router.post("/send-2fa-otp")
def send_2fa_otp(request: Send2FAOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.auth_method == "email":
        otp = generate_otp()
        store_otp(request.contact, otp)
        send_email_otp(request.contact, otp)
    elif request.auth_method == "phone":
        # For phone, you would trigger Firebase OTP from frontend
        # This is just a placeholder for backend tracking
        send_firebase_otp(request.contact)
    
    return {"message": f"OTP sent to {request.auth_method}"}


@router.post("/verify-2fa-otp")
def verify_2fa_otp(request: Verify2FAOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_valid = False
    
    if request.auth_method == "email":
        is_valid = verify_email_otp(request.email, request.otp_code)
    elif request.auth_method == "phone":
        # For phone verification, you might need a different approach
        # This is simplified - in production you'd verify the Firebase token
        is_valid = True  # Placeholder - implement proper phone verification
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Update user's 2FA contact method if needed
    if request.auth_method == "phone":
        user.phone_number = request.contact if hasattr(request, 'contact') else user.phone_number
    
    db.commit()
    
    return {"message": "2FA verification successful"}



@router.post("/resend-2fa-otp")
def resend_2fa_otp(request: Send2FAOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.auth_method == "email":
        otp = generate_otp()
        store_otp(request.contact, otp)
        send_email_otp(request.contact, otp)
    elif request.auth_method == "phone":
        send_firebase_otp(request.contact)
    
    return {"message": f"OTP resent to {request.auth_method}"}


@router.post("/resend-login-otp")
def resend_login_otp(request: Send2FAOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled for this user")

    # Send OTP based on user's registered method
    if user.auth_method == "email":
        otp = generate_otp()
        store_otp(user.email, otp)
        send_email_otp(user.email, otp)
    elif user.auth_method == "phone":
        send_firebase_otp(user.phone_number)
    
    return {"message": f"OTP resent to {user.auth_method}"}

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

@router.post("/login")
def login_user(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not bcrypt.verify(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # ✅ Check email verification BEFORE allowing login
    if not user.is_verified:
        raise HTTPException(
            status_code=403, 
            detail="Please verify your email before logging in. Check your inbox for the verification link."
        )

    # Handle 2FA - Send OTP and return 2FA info
    if user.is_2fa_enabled:
        print(f"[DEBUG LOGIN] 2FA enabled for {user.email}, method: {user.auth_method}")
        
        # Send OTP to user's registered method
        if user.auth_method == "phone":
            send_firebase_otp(user.phone_number)
            contact_info = user.phone_number
        elif user.auth_method == "email":
            otp = generate_otp()
            store_otp(user.email, otp)
            send_email_otp(user.email, otp)
            contact_info = user.email
        else:
            # Fallback to email if no method specified
            otp = generate_otp()
            store_otp(user.email, otp)
            send_email_otp(user.email, otp)
            contact_info = user.email
        
        # Return 2FA required response
        return {
            "requires_2fa": True,
            "auth_method": user.auth_method or "email",
            "contact": contact_info,
            "message": "2FA enabled. Please verify with the OTP sent to your registered method."
        }

    # For users without 2FA, complete login immediately
    # ✅ Update login tracking and check if first-time login
    is_first_login = update_login_tracking(user, db)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "requires_2fa": False,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
        "is_first_login": is_first_login,  # ✅ Frontend will use this to show pricing
        "login_count": user.login_count
    }


    

@router.post("/complete-login")
def complete_login_after_2fa(request: Verify2FAOTPRequest, db: Session = Depends(get_db)):
    print(f"[DEBUG] Complete login request: {request}")
    
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify OTP
    is_valid = False
    
    if request.auth_method == "email":
        is_valid = verify_email_otp(request.email, request.otp_code)
    elif request.auth_method == "phone":
        if request.otp_code == "firebase_verified":
            is_valid = True  # Placeholder
            print(f"✅ Phone OTP verified via Firebase for {request.email}")

        # For phone verification - implement proper phone verification
       
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # ✅ Update login tracking and check if first-time login
    is_first_login = update_login_tracking(user, db)

    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
        "is_first_login": is_first_login,  # ✅ Frontend will use this to show pricing
        "login_count": user.login_count
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

    try:
        send_password_reset_email(user.email, token)
    except Exception as e:
        print(f"Failed to send reset email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send reset email")

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
@router.post("/logout")
def logout_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        blacklist_token(token, db)
        return {"message": "Successfully logged out."}
    except Exception as e:
        print(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Failed to logout")


# ✅ NEW: Endpoint to mark pricing flow as completed
@router.post("/complete-pricing-flow")
def complete_pricing_flow(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Mark that user has completed the pricing flow"""
    from app.utils.token import decode_token, is_token_blacklisted
    
    if is_token_blacklisted(token, db):
        raise HTTPException(status_code=401, detail="Token is blacklisted")

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # This endpoint can be called when user dismisses pricing screen
        # or completes a subscription
        return {"message": "Pricing flow acknowledged"}
        
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# ------------------ GET CURRENT USER (Updated) ------------------
@router.get("/me", response_model=UserInfo)
def get_current_user_info(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.utils.token import decode_token, is_token_blacklisted
    
    if is_token_blacklisted(token, db):
        raise HTTPException(status_code=401, detail="Token is blacklisted")

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserInfo(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            is_2fa_enabled=user.is_2fa_enabled,
            auth_method=user.auth_method,
            phone_number=user.phone_number,
            # ✅ Add these new fields
            login_count=getattr(user, 'login_count', 0),
            first_login_completed=getattr(user, 'first_login_completed', False)
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# app/routers/auth.py - Add these routes

@router.post("/google-signup")
def google_signup(request: dict, db: Session = Depends(get_db)):
    """Handle Google signup for both web and native"""
    try:
        firebase_uid = request.get('firebase_uid')
        email = request.get('email')
        full_name = request.get('full_name')
        platform = request.get('platform', 'unknown')
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create new user
        new_user = User(
            full_name=full_name,
            email=email,
            password='',  # No password for Google users
            is_verified=True,  # Google accounts are pre-verified
            is_2fa_enabled=False,  # Default false
            auth_method='google',
            firebase_uid=firebase_uid,
            signup_platform=platform  # Track signup platform
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {
            "id": new_user.id,
            "message": "Google signup successful",
            "platform": platform,
            "user": {
                "email": new_user.email,
                "full_name": new_user.full_name
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/google-login")
def google_login(request: dict, db: Session = Depends(get_db)):
    """Handle Google login for both web and native"""
    try:
        firebase_uid = request.get('firebase_uid')
        email = request.get('email')
        platform = request.get('platform', 'unknown')
        
        # Find user
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found. Please sign up first.")
        
        # Update login tracking
        is_first_login = update_login_tracking(user, db)
        
        # Create tokens
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
            "is_first_login": is_first_login,
            "login_count": user.login_count,
            "platform": platform
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

        