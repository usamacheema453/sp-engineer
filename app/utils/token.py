from itsdangerous import URLSafeTimedSerializer
import os
from app.models.blacklist import BlacklistedToken
from sqlalchemy.orm import Session

SECRET_KEY = os.getenv("SECRET_KEY")
SECURITY_SALT = "email-confirm-salt"
# SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret")

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

def confirm_reset_token(token: str, expiration=3600):  # 1 hour default
    serializer = URLSafeTimedSerializer(SECRET_KEY)
    try:
        return serializer.loads(token, salt=SECURITY_SALT, max_age=expiration)
    except Exception:
        return None

#logout functionality of it.
def is_token_blacklisted(token: str, db: Session) -> bool:
    return db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first() is not None

def blacklist_token(token: str, db: Session):
    if not is_token_blacklisted(token, db):
        db.add(BlacklistedToken(token=token))
        db.commit()
