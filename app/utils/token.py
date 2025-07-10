# app/utils/token.py

from itsdangerous import URLSafeTimedSerializer
from jose import jwt, JWTError
import os
from app.models.blacklist import BlacklistedToken
from sqlalchemy.orm import Session

SECRET_KEY = os.getenv("SECRET_KEY", "your_secret_key_fallback")
SECURITY_SALT = "email-confirm-salt"
ALGORITHM = "HS256"

def generate_email_token(email):
    return URLSafeTimedSerializer(SECRET_KEY).dumps(email, salt=SECURITY_SALT)

def confirm_email_token(token, expiration=3600):
    try:
        return URLSafeTimedSerializer(SECRET_KEY).loads(token, salt=SECURITY_SALT, max_age=expiration)
    except Exception:
        return None

def generate_reset_token(email: str) -> str:
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    return serializer.dumps(email, salt=SECURITY_SALT)

def confirm_reset_token(token: str, expiration=3600):
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    try:
        return serializer.loads(token, salt=SECURITY_SALT, max_age=expiration)
    except Exception:
        return None

def decode_token(token: str):
    """Decode JWT token and return payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def is_token_blacklisted(token: str, db: Session) -> bool:
    return db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first() is not None

def blacklist_token(token: str, db: Session):
    if not is_token_blacklisted(token, db):
        db.add(BlacklistedToken(token=token))
        db.commit()