import os
import smtplib
from email.mime.text import MIMEText
from app.utils.token import generate_email_token

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM")

def send_verification_email(email: str):
    token = generate_email_token(email)
    link = f"http://localhost:8000/auth/verify-email?token={token}"
    body = f"Click the link to verify your email:\n\n{link}"

    msg = MIMEText(body)
    msg['Subject'] = "Verify your Email"
    msg['From'] = EMAIL_FROM
    msg['To'] = email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, email, msg.as_string())
