# app/utils/email.py - Professional Email Service with HTML Templates

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
EMAIL_FROM = os.getenv("EMAIL_FROM") or EMAIL_USER
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8081")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

otp_store = {}  # In-memory store for email OTPs

# ✅ PROFESSIONAL EMAIL TEMPLATE BASE
def get_email_template(title: str, content: str, action_button: str = None, action_url: str = None, footer_text: str = None) -> str:
    """Generate professional HTML email template"""
    
    # Action button HTML
    action_button_html = ""
    if action_button and action_url:
        action_button_html = f'''
        <div style="text-align: center; margin: 30px 0;">
            <a href="{action_url}" 
               style="background-color: #007bff; color: white; padding: 12px 30px; 
                      text-decoration: none; border-radius: 8px; font-weight: bold; 
                      display: inline-block; font-size: 16px;">
                {action_button}
            </a>
        </div>
        '''
    
    # Footer text
    footer_html = footer_text or "Need help? Contact us at support@superengineer.com"
    
    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; font-weight: bold;">
                    🚀 SuperEngineer
                </h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 16px;">
                    Your AI Assistant Platform
                </p>
            </div>
            
            <!-- Content -->
            <div style="padding: 40px 30px;">
                <h2 style="color: #333; margin-top: 0; font-size: 24px; margin-bottom: 20px;">
                    {title}
                </h2>
                
                <div style="color: #555; line-height: 1.6; font-size: 16px;">
                    {content}
                </div>
                
                {action_button_html}
                
                <!-- Divider -->
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                
                <!-- Security Notice -->
                <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff;">
                    <p style="margin: 0; color: #666; font-size: 14px;">
                        <strong>🔒 Security Notice:</strong> If you didn't request this action, please ignore this email or contact our support team immediately.
                    </p>
                </div>
            </div>
            
            <!-- Footer -->
            <div style="background-color: #f8f9fa; padding: 30px; text-align: center; border-top: 1px solid #eee;">
                <p style="margin: 0 0 10px 0; color: #666; font-size: 14px;">
                    {footer_html}
                </p>
                <p style="margin: 0; color: #999; font-size: 12px;">
                    © {datetime.now().year} SuperEngineer. All rights reserved.
                </p>
                <div style="margin-top: 15px;">
                    <a href="#" style="color: #007bff; text-decoration: none; margin: 0 10px; font-size: 12px;">Privacy Policy</a>
                    <a href="#" style="color: #007bff; text-decoration: none; margin: 0 10px; font-size: 12px;">Terms of Service</a>
                    <a href="#" style="color: #007bff; text-decoration: none; margin: 0 10px; font-size: 12px;">Unsubscribe</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

# ✅ OTP EMAIL TEMPLATE
def get_otp_template(otp: str, user_name: str = None) -> str:
    """Generate OTP email template"""
    greeting = f"Hi {user_name}," if user_name else "Hi there,"
    
    content = f'''
    <p>{greeting}</p>
    
    <p>You've requested a verification code for your SuperEngineer account. Please use the code below to complete your login:</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <div style="background-color: #f8f9fa; border: 2px dashed #007bff; padding: 20px; 
                    border-radius: 10px; display: inline-block;">
            <span style="font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 8px;">
                {otp}
            </span>
        </div>
    </div>
    
    <p><strong>⏰ This code will expire in 10 minutes.</strong></p>
    
    <p>For your security, never share this code with anyone. Our team will never ask for your verification code.</p>
    
    <p>Best regards,<br>
    The SuperEngineer Team</p>
    '''
    
    return get_email_template(
        title="🔐 Your Verification Code",
        content=content,
        footer_text="This verification code was requested for your SuperEngineer account."
    )

# ✅ WELCOME EMAIL TEMPLATE  
def get_welcome_template(user_name: str, verification_url: str) -> str:
    """Generate welcome email template"""
    content = f'''
    <p>Hi {user_name},</p>
    
    <p>🎉 <strong>Welcome to SuperEngineer!</strong> We're excited to have you join our community of innovators and AI enthusiasts.</p>
    
    <p>To get started and secure your account, please verify your email address by clicking the button below:</p>
    
    
    <p><strong>Your verification link will expire in 24 hours</strong> for security purposes.</p>
    
    <p>If you have any questions, our support team is here to help!</p>
    
    <p>Best regards,<br>
    The SuperEngineer Team</p>
    '''
    
    return get_email_template(
        title="🎉 Welcome to SuperEngineer!",
        content=content,
        action_button="Verify Email Address",
        action_url=verification_url,
        footer_text="Welcome aboard! We're here to help you succeed."
    )

# ✅ PASSWORD RESET TEMPLATE
def get_password_reset_template(user_name: str, reset_url: str) -> str:
    """Generate password reset email template"""
    content = f'''
    <p>Hi {user_name},</p>
    
    <p>We received a request to reset the password for your SuperEngineer account.</p>
    
    <p>If you made this request, click the button below to create a new password:</p>
    
    <div style="background-color: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107; margin: 20px 0;">
        <p style="margin: 0; color: #856404;">
            <strong>⏰ Important:</strong> This link will expire in 1 hour for your security.
        </p>
    </div>
    
    <p>If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
    
    <p>For security reasons, if you continue to receive unwanted password reset emails, please contact our support team.</p>
    
    <p>Best regards,<br>
    The SuperEngineer Team</p>
    '''
    
    return get_email_template(
        title="🔑 Reset Your Password",
        content=content,
        action_button="Reset Password",
        action_url=reset_url,
        footer_text="Reset link expires in 1 hour for your security."
    )

# ✅ SUBSCRIPTION TEMPLATES
def get_subscription_welcome_template(user_name: str, plan_name: str, billing_cycle: str, amount: float) -> str:
    """Generate subscription welcome email"""
    content = f'''
    <p>Hi {user_name},</p>
    
    <p>🎉 <strong>Thank you for upgrading to {plan_name}!</strong> Your subscription is now active and ready to use.</p>
    
    <div style="background-color: #d4edda; padding: 20px; border-radius: 8px; border-left: 4px solid #28a745; margin: 20px 0;">
        <h3 style="color: #155724; margin: 0 0 15px 0;">📋 Subscription Details</h3>
        <ul style="margin: 0; padding-left: 20px; color: #155724;">
            <li><strong>Plan:</strong> {plan_name}</li>
            <li><strong>Billing:</strong> ${amount:.2f} {billing_cycle}</li>
            <li><strong>Next Billing:</strong> {(datetime.now() + timedelta(days=365 if billing_cycle == 'yearly' else 30)).strftime('%B %d, %Y')}</li>
            <li><strong>Status:</strong> Active ✅</li>
        </ul>
    </div>
    
    <p><strong>🚀 You now have access to:</strong></p>
    <ul style="color: #555; padding-left: 20px;">
        <li>Enhanced AI capabilities</li>
        <li>Priority support</li>
        <li>Advanced features</li>
        <li>Increased usage limits</li>
    </ul>
    
    <p>Your subscription will automatically renew unless you choose to cancel. You can manage your subscription anytime in your account settings.</p>
    
    <p>Thank you for choosing SuperEngineer!</p>
    
    <p>Best regards,<br>
    The SuperEngineer Team</p>
    '''
    
    return get_email_template(
        title=f"✅ {plan_name} Subscription Activated!",
        content=content,
        action_button="Access Dashboard",
        action_url=f"{FRONTEND_URL}/dashboard",
        footer_text=f"Your {plan_name} subscription is now active!"
    )

# ✅ RENEWAL SUCCESS TEMPLATE
def get_renewal_success_template(user_name: str, plan_name: str, amount: float, next_billing: str) -> str:
    """Generate renewal success email"""
    content = f'''
    <p>Hi {user_name},</p>
    
    <p>✅ <strong>Your {plan_name} subscription has been successfully renewed!</strong></p>
    
    <div style="background-color: #d1ecf1; padding: 20px; border-radius: 8px; border-left: 4px solid #17a2b8; margin: 20px 0;">
        <h3 style="color: #0c5460; margin: 0 0 15px 0;">💳 Payment Confirmation</h3>
        <ul style="margin: 0; padding-left: 20px; color: #0c5460;">
            <li><strong>Amount Charged:</strong> ${amount:.2f}</li>
            <li><strong>Plan:</strong> {plan_name}</li>
            <li><strong>Payment Date:</strong> {datetime.now().strftime('%B %d, %Y')}</li>
            <li><strong>Next Billing:</strong> {next_billing}</li>
        </ul>
    </div>
    
    <p>Your service will continue uninterrupted. Thank you for being a valued SuperEngineer subscriber!</p>
    
    <p>You can view your payment history and manage your subscription anytime in your account settings.</p>
    
    <p>Best regards,<br>
    The SuperEngineer Team</p>
    '''
    
    return get_email_template(
        title="✅ Subscription Renewed Successfully",
        content=content,
        action_button="View Payment History",
        action_url=f"{FRONTEND_URL}/settings/billing",
        footer_text="Thank you for your continued trust in SuperEngineer!"
    )

# ✅ CANCELLATION CONFIRMATION TEMPLATE
def get_cancellation_template(user_name: str, plan_name: str, access_until: str, remaining_days: int) -> str:
    """Generate cancellation confirmation email"""
    content = f'''
    <p>Hi {user_name},</p>
    
    <p>We've received your request to cancel your {plan_name} subscription. Your cancellation has been processed.</p>
    
    <div style="background-color: #f8d7da; padding: 20px; border-radius: 8px; border-left: 4px solid #dc3545; margin: 20px 0;">
        <h3 style="color: #721c24; margin: 0 0 15px 0;">📋 Cancellation Details</h3>
        <ul style="margin: 0; padding-left: 20px; color: #721c24;">
            <li><strong>Plan:</strong> {plan_name}</li>
            <li><strong>Cancelled On:</strong> {datetime.now().strftime('%B %d, %Y')}</li>
            <li><strong>Access Until:</strong> {access_until}</li>
            <li><strong>Remaining Days:</strong> {remaining_days} days</li>
        </ul>
    </div>
    
    <p><strong>🔄 What happens next:</strong></p>
    <ul style="color: #555; padding-left: 20px;">
        <li>You'll retain full access until {access_until}</li>
        <li>No further charges will be made</li>
        <li>You can reactivate anytime before {access_until}</li>
        <li>Your data will be preserved</li>
    </ul>
    
    <p>We're sorry to see you go! If you have any feedback on how we can improve, we'd love to hear from you.</p>
    
    <p>Best regards,<br>
    The SuperEngineer Team</p>
    '''
    
    return get_email_template(
        title="✅ Subscription Cancelled",
        content=content,
        action_button="Provide Feedback",
        action_url=f"{FRONTEND_URL}/feedback",
        footer_text="We hope to see you back soon!"
    )

# ✅ ENHANCED EMAIL SENDER
def send_email(to: str, subject: str, body: str, is_html: bool = True):
    """Enhanced email sender with HTML support"""
    msg = MIMEMultipart('alternative')
    msg["From"] = f"SuperEngineer <{EMAIL_FROM}>"
    msg["To"] = to
    msg["Subject"] = subject
    
    if is_html:
        # Create plain text version from HTML (basic conversion)
        import re
        plain_text = re.sub('<[^<]+?>', '', body)
        plain_text = re.sub(r'\s+', ' ', plain_text).strip()
        
        # Attach both versions
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, to, msg.as_string())
            print(f"[EMAIL SENT] To: {to} | Subject: {subject}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to}: {e}")

# ✅ UPDATED EMAIL FUNCTIONS

def send_verification_email(email: str, user_name: str = None):
    """Send professional verification email"""
    token = generate_email_token(email)
    verification_url = f"{BACKEND_URL}/auth/verify-email?token={token}"
    
    if not user_name:
        user_name = email.split('@')[0].title()
    
    html_body = get_welcome_template(user_name, verification_url)
    send_email(email, "🎉 Welcome to SuperEngineer - Verify Your Email", html_body)

def send_password_reset_email(email: str, token: str, user_name: str = None):
    """Send professional password reset email"""
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    
    if not user_name:
        user_name = email.split('@')[0].title()
    
    html_body = get_password_reset_template(user_name, reset_url)
    send_email(email, "🔑 Reset Your SuperEngineer Password", html_body)

def send_email_otp(email: str, otp: str, user_name: str = None):
    """Send professional OTP email"""
    if not user_name:
        user_name = email.split('@')[0].title()
    
    html_body = get_otp_template(otp, user_name)
    send_email(email, "🔐 Your SuperEngineer Verification Code", html_body)

def send_subscription_welcome_email(user_name: str, plan_name: str, billing_cycle: str, amount: float, user_email: str):
    """Send subscription welcome email"""
    html_body = get_subscription_welcome_template(user_name, plan_name, billing_cycle, amount)
    send_email(user_email, f"✅ Welcome to {plan_name}! Your Subscription is Active", html_body)

def send_renewal_success_email(user_name: str, plan_name: str, amount: float, next_billing: str, user_email: str):
    """Send renewal success email"""
    html_body = get_renewal_success_template(user_name, plan_name, amount, next_billing)
    send_email(user_email, f"✅ {plan_name} Subscription Renewed Successfully", html_body)

def send_cancellation_email(user_name: str, plan_name: str, access_until: str, remaining_days: int, user_email: str):
    """Send cancellation confirmation email"""
    html_body = get_cancellation_template(user_name, plan_name, access_until, remaining_days)
    send_email(user_email, "✅ Subscription Cancellation Confirmed", html_body)

# ✅ KEEP EXISTING FUNCTIONS FOR COMPATIBILITY
def generate_otp():
    return str(random.randint(100000, 999999))

def store_otp(email: str, otp: str, expiry_minutes: int = 10):
    expiry = datetime.utcnow() + timedelta(minutes=expiry_minutes)
    otp_store[email] = (otp, expiry)

def verify_email_otp(email: str, otp: str) -> bool:
    print(f"[DEBUG OTP] Verifying OTP for email: {email}")
    print(f"[DEBUG OTP] Provided OTP: {otp}")
    
    stored = otp_store.get(email)
    if not stored:
        print(f"[DEBUG OTP] No OTP found in store for {email}")
        return False
    
    stored_otp, expiry = stored
    print(f"[DEBUG OTP] Stored OTP: {stored_otp}, Expiry: {expiry}")
    
    if datetime.utcnow() > expiry:
        print(f"[DEBUG OTP] OTP expired for {email}")
        del otp_store[email]
        return False
    
    is_match = otp == stored_otp
    print(f"[DEBUG OTP] OTP match result: {is_match}")
    
    if is_match:
        del otp_store[email]
        print(f"[DEBUG OTP] OTP verified and cleaned up for {email}")
    
    return is_match