from itsdangerous import URLSafeTimedSerializer
import os

SECRET_KEY = os.getenv("SECRET_KEY")
SECURITY_SALT = "email-confirm-salt"

def generate_email_token(email):
    return URLSafeTimedSerializer(SECRET_KEY).dumps(email, salt=SECURITY_SALT)

def confirm_email_token(token, expiration=3600):
    try:
        return URLSafeTimedSerializer(SECRET_KEY).loads(token, salt=SECURITY_SALT, max_age=expiration)
    except Exception:
        return None
