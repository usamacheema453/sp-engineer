import os
import smtplib
from email.mime.text import MIMEText
from app.utils.token import generate_email_token
from email.mime.multipart import MIMEMultipart

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


def send_email(to: str, subject: str, body: str):
    sender = "your_email@gmail.com"
    password = "your_app_password"  # App password for Gmail

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, to, msg.as_string())
        server.quit()
        print(f"Email sent to {to}")
    except Exception as e:
        print(f"Email failed: {e}")

def send_password_reset_email(email: str, token: str):
    reset_link = f"http://yourfrontend.com/reset-password?token={token}"
    # Replace with actual email service
    print(f"[DEBUG] Send this to {email}:\nReset your password: {reset_link}")
