import os
import smtplib
import random
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.utils.token import generate_email_token

# Load credentials from environment
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM") or EMAIL_USER  # fallback

otp_store = {}  # In-memory store for email OTPs


# ✅ 1. Send email verification link
def send_verification_email(email: str):
    token = generate_email_token(email)
    link = f"http://localhost:8000/auth/verify-email?token={token}"
    body = f"Click the link to verify your email:\n\n{link}"

    send_email(email, "Verify your Email", body)


# ✅ 2. Generic email sender (used by other functions)
def send_email(to: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, to, msg.as_string())
            print(f"[EMAIL SENT] To: {to}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to}: {e}")


# ✅ 3. Password reset email
def send_password_reset_email(email: str, token: str):
    reset_link = f"http://yourfrontend.com/reset-password?token={token}"
    body = f"Reset your password using this link:\n\n{reset_link}"
    send_email(email, "Reset Your Password", body)


# ✅ 4. OTP Generation
def generate_otp():
    return str(random.randint(100000, 999999))


# ✅ 5. Send OTP via email
def send_email_otp(email: str, otp: str):
    subject = "Your 2FA Verification Code"
    body = f"Your verification code is: {otp}\n\nThis code will expire in 10 minutes."
    send_email(email, subject, body)


# ✅ 6. Store OTP for email
def store_otp(email: str, otp: str, expiry_minutes: int = 10):
    expiry = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    otp_store[email] = (otp, expiry)


# ✅ 7. Verify OTP from user
def verify_email_otp(email: str, otp: str) -> bool:
    print(f"[DEBUG OTP] Verifying OTP for email: {email}")
    print(f"[DEBUG OTP] Provided OTP: {otp}")
    print(f"[DEBUG OTP] Current OTP store: {otp_store}")
    
    stored = otp_store.get(email)
    if not stored:
        print(f"[DEBUG OTP] No OTP found in store for {email}")
        return False
    
    stored_otp, expiry = stored
    print(f"[DEBUG OTP] Stored OTP: {stored_otp}, Expiry: {expiry}")
    print(f"[DEBUG OTP] Current time: {datetime.utcnow()}")
    
    if datetime.utcnow() > expiry:
        print(f"[DEBUG OTP] OTP expired for {email}")
        del otp_store[email]
        return False
    
    is_match = otp == stored_otp
    print(f"[DEBUG OTP] OTP match result: {is_match}")
    
    if is_match:
        # Clean up used OTP
        del otp_store[email]
        print(f"[DEBUG OTP] OTP verified and cleaned up for {email}")
    
    return is_match