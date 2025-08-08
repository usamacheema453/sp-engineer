from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.user_settings import UserSettings
from passlib.hash import bcrypt
from app.models.subscription import UserSubscription, PaymentHistory, SubscriptionPlan
from typing import List

from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import io
import os
from pathlib import Path
from fastapi import Query
from app.utils.token import decode_token

router = APIRouter(prefix="/user-settings", tags=["User Settings"])

# ✅ UPDATED SCHEMAS
from pydantic import BaseModel

class NotificationSettingsRequest(BaseModel):
    email_notifications: bool
    push_notifications: bool
    marketing_communications: bool

class PersonalizationSettingsRequest(BaseModel):
    profile_avatar: Optional[str] = None
    profession: Optional[str] = None
    industry: Optional[str] = None
    expertise_level: Optional[str] = None
    communication_tone: Optional[str] = None
    response_instructions: Optional[str] = None
    nickname: Optional[str] = None  # ✅ NEW: Added nickname

class Toggle2FARequest(BaseModel):
    is_2fa_enabled: bool

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# ✅ NEW: General settings update request
class GeneralSettingsRequest(BaseModel):
    phone_number: Optional[str] = None

# ✅ UPDATED: Main response with user data
class AllUserSettingsResponse(BaseModel):
    # ✅ NEW: User basic info
    full_name: str
    email: str
    phone_number: Optional[str]
    nickname: Optional[str]
    
    # Notifications
    email_notifications: bool
    push_notifications: bool
    marketing_communications: bool
    
    # Personalization
    profile_avatar: Optional[str]
    profession: Optional[str]
    industry: Optional[str]
    expertise_level: str
    communication_tone: str
    response_instructions: Optional[str]
    
    # Security (from main User table)
    is_2fa_enabled: bool
    
    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaymentHistoryItem(BaseModel):
    payment_id: str
    plan_name: str
    purchase_date: str  # ISO format date
    amount: float  # Amount in dollars
    status: str  # "Paid", "Failed", "Pending"
    plan_start_date: str  # ISO format date
    plan_expire_date: str  # ISO format date
    billing_cycle: str  # "monthly" or "yearly"

class PaymentHistoryResponse(BaseModel):
    success: bool
    message: str
    total_payments: int
    payment_history: List[PaymentHistoryItem]

# ✅ HELPER FUNCTIONS
def get_or_create_user_settings(db: Session, user_id: int) -> UserSettings:
    """Get user settings, create if doesn't exist"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    
    if not settings:
        print(f"Creating default settings for user {user_id}")
        settings = UserSettings(
            user_id=user_id,
            email_notifications=True,
            push_notifications=True,
            marketing_communications=False,
            expertise_level="intermediate",
            communication_tone="casual_friendly"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
        print(f"✅ Default settings created for user {user_id}")
    
    return settings

# ✅ MAIN ENDPOINTS

# ✅ IMPORTANT: Specific routes MUST come before generic "/" route to avoid conflicts

# ✅ NEW: General settings endpoints (MOVED UP)
@router.get("/general")
def get_general_settings(
    current_user: User = Depends(get_current_user)
):
    """Get general user settings (phone, name, email)"""
    try:
        return {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "nickname": current_user.nickname,
            "message": "General settings retrieved successfully!"
        }
    except Exception as e:
        print(f"❌ Error getting general settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get general settings: {str(e)}"
        )

@router.put("/general")
def update_general_settings(
    data: GeneralSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update general settings (phone number)"""
    try:
        print(f"Updating general settings for user {current_user.id}: {data}")
        
        # Update phone number if provided
        if data.phone_number is not None:
            current_user.phone_number = data.phone_number
        
        db.commit()
        db.refresh(current_user)
        
        print(f"✅ General settings updated for user {current_user.id}")
        
        return {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "nickname": current_user.nickname,
            "message": "General settings updated successfully!"
        }
    except Exception as e:
        print(f"❌ Error updating general settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update general settings: {str(e)}"
        )

@router.get("/notifications")
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications
        }
    except Exception as e:
        print(f"❌ Error getting notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification settings: {str(e)}"
        )

@router.get("/personalization")
def get_personalization_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalization settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname  # ✅ NEW: Added nickname from User table
        }
    except Exception as e:
        print(f"❌ Error getting personalization settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personalization settings: {str(e)}"
        )

@router.get("/security")
def get_security_settings(
    current_user: User = Depends(get_current_user)
):
    """Get security settings"""
    try:
        return {
            "is_2fa_enabled": current_user.is_2fa_enabled,
            "message": "Security settings retrieved successfully!"
        }
    except Exception as e:
        print(f"❌ Error getting security settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )

# ✅ Main endpoint - MUST be at the end to avoid route conflicts
@router.get("/", response_model=AllUserSettingsResponse)
def get_all_user_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all user settings including user basic info"""
    try:
        print(f"Getting settings for user {current_user.id}")
        
        # Get or create settings
        settings = get_or_create_user_settings(db, current_user.id)
        
        # ✅ UPDATED: Build response with user data
        response_data = {
            # ✅ NEW: User basic information
            "full_name": current_user.full_name,
            "email": current_user.email,
            "phone_number": current_user.phone_number,
            "nickname": current_user.nickname,
            
            # Notification settings
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications,
            
            # Personalization settings
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            
            # Security settings (from main User table)
            "is_2fa_enabled": current_user.is_2fa_enabled,
            
            # Metadata
            "created_at": settings.created_at,
            "updated_at": settings.updated_at
        }
        
        print(f"✅ Settings retrieved for user {current_user.id}")
        return AllUserSettingsResponse(**response_data)
        
    except Exception as e:
        print(f"❌ Error getting settings for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve settings: {str(e)}"
        )

@router.get("/notifications")
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications
        }
    except Exception as e:
        print(f"❌ Error getting notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification settings: {str(e)}"
        )

@router.put("/notifications")
def update_notification_settings(
    data: NotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification settings"""
    try:
        print(f"Updating notification settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update notification settings
        settings.email_notifications = data.email_notifications
        settings.push_notifications = data.push_notifications
        settings.marketing_communications = data.marketing_communications
        settings.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(settings)
        
        print(f"✅ Notification settings updated for user {current_user.id}")
        
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications,
            "message": "Notification settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating notification settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )

@router.get("/personalization")
def get_personalization_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalization settings"""
    try:
        settings = get_or_create_user_settings(db, current_user.id)
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname  # ✅ NEW: Added nickname from User table
        }
    except Exception as e:
        print(f"❌ Error getting personalization settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get personalization settings: {str(e)}"
        )

@router.put("/personalization")
def update_personalization_settings(
    data: PersonalizationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update personalization settings including nickname"""
    try:
        print(f"Updating personalization settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update UserSettings table fields
        if data.profile_avatar is not None:
            settings.profile_avatar = data.profile_avatar
        if data.profession is not None:
            settings.profession = data.profession
        if data.industry is not None:
            settings.industry = data.industry
        if data.expertise_level is not None:
            settings.expertise_level = data.expertise_level
        if data.communication_tone is not None:
            settings.communication_tone = data.communication_tone
        if data.response_instructions is not None:
            settings.response_instructions = data.response_instructions
        
        settings.updated_at = datetime.utcnow()
        
        # ✅ NEW: Update nickname in User table
        if data.nickname is not None:
            current_user.nickname = data.nickname
        
        db.commit()
        db.refresh(settings)
        db.refresh(current_user)
        
        print(f"✅ Personalization settings updated for user {current_user.id}")
        
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname,  # ✅ NEW: Return updated nickname
            "message": "Personalization settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating personalization settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personalization settings: {str(e)}"
        )

# ✅ UPDATE endpoints for specific sections
@router.put("/notifications")
def update_notification_settings(
    data: NotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification settings"""
    try:
        print(f"Updating notification settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update notification settings
        settings.email_notifications = data.email_notifications
        settings.push_notifications = data.push_notifications
        settings.marketing_communications = data.marketing_communications
        settings.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(settings)
        
        print(f"✅ Notification settings updated for user {current_user.id}")
        
        return {
            "email_notifications": settings.email_notifications,
            "push_notifications": settings.push_notifications,
            "marketing_communications": settings.marketing_communications,
            "message": "Notification settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating notification settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )

@router.put("/personalization")
def update_personalization_settings(
    data: PersonalizationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update personalization settings including nickname"""
    try:
        print(f"Updating personalization settings for user {current_user.id}: {data}")
        
        settings = get_or_create_user_settings(db, current_user.id)
        
        # Update UserSettings table fields
        if data.profile_avatar is not None:
            settings.profile_avatar = data.profile_avatar
        if data.profession is not None:
            settings.profession = data.profession
        if data.industry is not None:
            settings.industry = data.industry
        if data.expertise_level is not None:
            settings.expertise_level = data.expertise_level
        if data.communication_tone is not None:
            settings.communication_tone = data.communication_tone
        if data.response_instructions is not None:
            settings.response_instructions = data.response_instructions
        
        settings.updated_at = datetime.utcnow()
        
        # ✅ NEW: Update nickname in User table
        if data.nickname is not None:
            current_user.nickname = data.nickname
        
        db.commit()
        db.refresh(settings)
        db.refresh(current_user)
        
        print(f"✅ Personalization settings updated for user {current_user.id}")
        
        return {
            "profile_avatar": settings.profile_avatar,
            "profession": settings.profession,
            "industry": settings.industry,
            "expertise_level": settings.expertise_level,
            "communication_tone": settings.communication_tone,
            "response_instructions": settings.response_instructions,
            "nickname": current_user.nickname,  # ✅ NEW: Return updated nickname
            "message": "Personalization settings updated successfully!"
        }
        
    except Exception as e:
        print(f"❌ Error updating personalization settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update personalization settings: {str(e)}"
        )
def get_security_settings(
    current_user: User = Depends(get_current_user)
):
    """Get security settings"""
    try:
        return {
            "is_2fa_enabled": current_user.is_2fa_enabled,
            "message": "Security settings retrieved successfully!"
        }
    except Exception as e:
        print(f"❌ Error getting security settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )

@router.put("/security/2fa")
def toggle_2fa(
    data: Toggle2FARequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle 2FA on/off - FIXED VERSION"""
    try:
        print(f"🔐 Toggling 2FA for user {current_user.id}: {data.is_2fa_enabled}")
        
        # ✅ UPDATE THE USER'S 2FA STATUS
        current_user.is_2fa_enabled = data.is_2fa_enabled
        db.commit()
        db.refresh(current_user)
        
        status_text = "enabled" if data.is_2fa_enabled else "disabled"
        print(f"✅ 2FA {status_text} for user {current_user.id}")
        
        return {
            "is_2fa_enabled": current_user.is_2fa_enabled,
            "message": f"2FA successfully {status_text}!",
            "success": True
        }
    except Exception as e:
        print(f"❌ Error toggling 2FA: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update 2FA settings: {str(e)}"
        )


@router.post("/security/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        # Verify current password
        if not bcrypt.verify(data.current_password, current_user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect!"
            )
        
        # Hash and update new password
        hashed_password = bcrypt.hash(data.new_password)
        current_user.password = hashed_password
        db.commit()
        
        print(f"✅ Password changed for user {current_user.id}")
        
        return {
            "message": "Password changed successfully!",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error changing password: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )

# ✅ NEW ENDPOINT - Add this endpoint in user_settings.py router
@router.get("/payment-history", response_model=PaymentHistoryResponse)
def get_user_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get complete payment history for current user"""
    try:
        print(f"📊 Fetching payment history for user {current_user.id}")
        
        # Get all payment history records for user
        payment_records = db.query(PaymentHistory).filter(
            PaymentHistory.user_id == current_user.id
        ).order_by(PaymentHistory.payment_date.desc()).all()
        
        # Get all user subscriptions to map plan details
        user_subscriptions = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id
        ).all()
        
        payment_history_items = []
        
        for payment in payment_records:
            try:
                # Find corresponding subscription
                subscription = db.query(UserSubscription).filter(
                    UserSubscription.id == payment.subscription_id
                ).first()
                
                if not subscription:
                    print(f"⚠️ Subscription not found for payment {payment.id}")
                    continue
                
                # Get plan details
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == subscription.plan_id
                ).first()
                
                if not plan:
                    print(f"⚠️ Plan not found for subscription {subscription.id}")
                    continue
                
                # Determine status
                status = "Paid" if payment.status == "succeeded" else "Failed"
                if payment.status in ["pending", "processing"]:
                    status = "Pending"
                
                # Format billing cycle
                billing_cycle = "yearly" if subscription.billing_cycle.value == "yearly" else "monthly"
                
                # Create payment history item
                payment_item = PaymentHistoryItem(
                    payment_id=payment.payment_intent_id or f"payment_{payment.id}",
                    plan_name=plan.name,
                    purchase_date=payment.payment_date.isoformat() if payment.payment_date else "",
                    amount=float(payment.amount / 100),  # Convert cents to dollars
                    status=status,
                    plan_start_date=subscription.start_date.isoformat() if subscription.start_date else "",
                    plan_expire_date=subscription.expiry_date.isoformat() if subscription.expiry_date else "",
                    billing_cycle=billing_cycle
                )
                
                payment_history_items.append(payment_item)
                print(f"✅ Added payment record: {payment.payment_intent_id} - {plan.name}")
                
            except Exception as e:
                print(f"❌ Error processing payment record {payment.id}: {str(e)}")
                continue
        
        # Also include current active subscription if no payment history exists
        if len(payment_history_items) == 0:
            active_subscription = db.query(UserSubscription).filter(
                UserSubscription.user_id == current_user.id,
                UserSubscription.active == True
            ).first()
            
            if active_subscription:
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == active_subscription.plan_id
                ).first()
                
                if plan:
                    # Add active subscription as "current plan"
                    billing_cycle = "yearly" if active_subscription.billing_cycle.value == "yearly" else "monthly"
                    
                    payment_item = PaymentHistoryItem(
                        payment_id=active_subscription.last_payment_intent_id or f"sub_{active_subscription.id}",
                        plan_name=plan.name,
                        purchase_date=active_subscription.start_date.isoformat() if active_subscription.start_date else "",
                        amount=0.0 if plan.name == "Free" else (float(plan.yearly_price / 100) if billing_cycle == "yearly" else float(plan.monthly_price / 100)),
                        status="Paid",
                        plan_start_date=active_subscription.start_date.isoformat() if active_subscription.start_date else "",
                        plan_expire_date=active_subscription.expiry_date.isoformat() if active_subscription.expiry_date else "",
                        billing_cycle=billing_cycle
                    )
                    
                    payment_history_items.append(payment_item)
                    print(f"✅ Added current subscription: {plan.name}")
        
        print(f"📊 Total payment records found: {len(payment_history_items)}")
        
        return PaymentHistoryResponse(
            success=True,
            message="Payment history retrieved successfully",
            total_payments=len(payment_history_items),
            payment_history=payment_history_items
        )
        
    except Exception as e:
        print(f"❌ Error fetching payment history for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment history: {str(e)}"
        )

# ✅ SUMMARY ENDPOINT - Additional endpoint for payment summary
@router.get("/payment-summary")
def get_payment_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment summary statistics"""
    try:
        # Get total payments
        total_payments = db.query(PaymentHistory).filter(
            PaymentHistory.user_id == current_user.id
        ).count()
        
        # Get successful payments
        successful_payments = db.query(PaymentHistory).filter(
            PaymentHistory.user_id == current_user.id,
            PaymentHistory.status == "succeeded"
        ).count()
        
        # Calculate total amount spent
        payment_records = db.query(PaymentHistory).filter(
            PaymentHistory.user_id == current_user.id,
            PaymentHistory.status == "succeeded"
        ).all()
        
        total_spent = sum([payment.amount for payment in payment_records]) / 100  # Convert to dollars
        
        # Get current subscription
        current_subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.active == True
        ).first()
        
        current_plan = "No active plan"
        next_billing_date = None
        
        if current_subscription:
            plan = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.id == current_subscription.plan_id
            ).first()
            if plan:
                current_plan = plan.name
                next_billing_date = current_subscription.next_renewal_date.isoformat() if current_subscription.next_renewal_date else None
        
        return {
            "success": True,
            "summary": {
                "total_payments": total_payments,
                "successful_payments": successful_payments,
                "failed_payments": total_payments - successful_payments,
                "total_amount_spent": round(total_spent, 2),
                "current_plan": current_plan,
                "next_billing_date": next_billing_date
            }
        }
        
    except Exception as e:
        print(f"❌ Error fetching payment summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment summary: {str(e)}"
        )

@router.get("/download-invoice-public/{payment_id}")
def download_invoice_public(
    payment_id: str,
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db)
):
    """Public PDF download endpoint with token validation"""
    try:
        print(f"📄 Public PDF download for payment: {payment_id}")
        
        # Validate token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Get user
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        print(f"👤 User authenticated: {user.email}")
        
        # Find payment record
        payment_record = db.query(PaymentHistory).filter(
            PaymentHistory.payment_intent_id == payment_id,
            PaymentHistory.user_id == user.id
        ).first()
        
        subscription = None
        plan = None
        
        if not payment_record:
            # Try to find by subscription
            subscription = db.query(UserSubscription).filter(
                UserSubscription.last_payment_intent_id == payment_id,
                UserSubscription.user_id == user.id
            ).first()
            
            if subscription:
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == subscription.plan_id
                ).first()
                
                payment_data = {
                    'id': payment_id,
                    'amount': plan.monthly_price if subscription.billing_cycle.value == 'monthly' else plan.yearly_price,
                    'date': subscription.start_date,
                    'plan': plan.name,
                    'billing_cycle': subscription.billing_cycle.value,
                    'status': 'succeeded'
                }
            else:
                raise HTTPException(status_code=404, detail="Payment record not found")
        else:
            subscription = db.query(UserSubscription).filter(
                UserSubscription.id == payment_record.subscription_id
            ).first()
            
            plan = db.query(SubscriptionPlan).filter(
                SubscriptionPlan.id == subscription.plan_id
            ).first()
            
            payment_data = {
                'id': payment_record.payment_intent_id,
                'amount': payment_record.amount,
                'date': payment_record.payment_date,
                'plan': plan.name,
                'billing_cycle': payment_record.billing_cycle.value,
                'status': payment_record.status
            }
        
        # Generate PDF
        pdf_path = generate_invoice_pdf(user, payment_data, subscription, plan)
        
        print(f"✅ PDF generated successfully for {user.email}")
        
        return FileResponse(
            path=pdf_path,
            filename=f"SuperEngineer_Invoice_{payment_id[-8:]}.pdf",
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in public PDF download: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

        
def generate_invoice_pdf(user: User, payment_data: dict, subscription: UserSubscription, plan: SubscriptionPlan):
    """Generate PDF invoice"""
    
    # Create temp directory if not exists
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    
    # Generate PDF path
    pdf_filename = f"invoice_{payment_data['id'][-8:]}.pdf"
    pdf_path = temp_dir / pdf_filename
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#000000'),
        alignment=1  # Center alignment
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#000000')
    )
    
    # Build PDF content
    story = []
    
    # Company Header
    story.append(Paragraph("SuperEngineer", title_style))
    story.append(Paragraph("Invoice", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Invoice Details Table
    invoice_data = [
        ['Invoice Number:', f"INV-{payment_data['id'][-8:]}"],
        ['Invoice Date:', payment_data['date'].strftime('%B %d, %Y') if payment_data['date'] else 'N/A'],
        ['Payment Status:', payment_data['status'].title()],
        ['Payment ID:', payment_data['id']],
    ]
    
    invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(invoice_table)
    story.append(Spacer(1, 30))
    
    # Bill To Section
    story.append(Paragraph("Bill To:", header_style))
    
    customer_data = [
        ['Name:', user.full_name],
        ['Email:', user.email],
        ['Phone:', user.phone_number or 'N/A'],
    ]
    
    customer_table = Table(customer_data, colWidths=[1*inch, 4*inch])
    customer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(customer_table)
    story.append(Spacer(1, 30))
    
    # Services Table
    story.append(Paragraph("Services:", header_style))
    
    # Calculate dates
    start_date = subscription.start_date.strftime('%b %d, %Y') if subscription.start_date else 'N/A'
    end_date = subscription.expiry_date.strftime('%b %d, %Y') if subscription.expiry_date else 'N/A'
    
    services_data = [
        ['Description', 'Period', 'Amount'],
        [
            f"{payment_data['plan']} Plan ({payment_data['billing_cycle'].title()})",
            f"{start_date} - {end_date}",
            f"${payment_data['amount'] / 100:.2f}"
        ],
    ]
    
    services_table = Table(services_data, colWidths=[3*inch, 2*inch, 1*inch])
    services_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8F9FA')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),  # Amount column right-aligned
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        # Grid
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(services_table)
    story.append(Spacer(1, 20))
    
    # Total Section
    total_data = [
        ['Subtotal:', f"${payment_data['amount'] / 100:.2f}"],
        ['Tax:', '$0.00'],
        ['Total:', f"${payment_data['amount'] / 100:.2f}"],
    ]
    
    total_table = Table(total_data, colWidths=[4*inch, 1*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Bold total row
        ('FONTSIZE', (0, -1), (-1, -1), 14),  # Larger font for total
        ('FONTSIZE', (0, 0), (-1, -2), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Line above total
    ]))
    
    story.append(total_table)
    story.append(Spacer(1, 40))
    
    # Footer
    footer_text = """
    <para alignment="center">
    <b>Thank you for your business!</b><br/>
    For questions about this invoice, please contact support@superengineer.com<br/>
    SuperEngineer - Your AI Assistant Platform
    </para>
    """
    
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    
    print(f"✅ PDF generated: {pdf_path}")
    return str(pdf_path)

# ✅ HELPER ENDPOINT - Get payment summary for invoice generation
@router.get("/invoice-data/{payment_id}")
def get_invoice_data(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get invoice data for specific payment (for frontend preview)"""
    try:
        # Find payment record
        payment_record = db.query(PaymentHistory).filter(
            PaymentHistory.payment_intent_id == payment_id,
            PaymentHistory.user_id == current_user.id
        ).first()
        
        if not payment_record:
            raise HTTPException(status_code=404, detail="Payment record not found")
        
        # Get subscription and plan details
        subscription = db.query(UserSubscription).filter(
            UserSubscription.id == payment_record.subscription_id
        ).first()
        
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription.plan_id
        ).first()
        
        return {
            "success": True,
            "invoice_data": {
                "invoice_number": f"INV-{payment_record.payment_intent_id[-8:]}",
                "payment_id": payment_record.payment_intent_id,
                "amount": payment_record.amount / 100,
                "plan_name": plan.name,
                "billing_cycle": payment_record.billing_cycle.value,
                "payment_date": payment_record.payment_date.isoformat(),
                "status": payment_record.status,
                "period": {
                    "start": subscription.start_date.isoformat() if subscription.start_date else None,
                    "end": subscription.expiry_date.isoformat() if subscription.expiry_date else None
                },
                "customer": {
                    "name": current_user.full_name,
                    "email": current_user.email,
                    "phone": current_user.phone_number
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting invoice data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get invoice data: {str(e)}"
        )


# ✅ DEBUG ENDPOINTS (Remove in production)
@router.get("/debug/test")
def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "status": "ok",
        "message": "User Settings API is working!",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/debug/auth-test")
def test_auth_endpoint(current_user: User = Depends(get_current_user)):
    """Test authentication"""
    return {
        "status": "authenticated",
        "user_id": current_user.id,
        "user_email": current_user.email,
        "user_full_name": current_user.full_name,  # ✅ NEW: Added for debugging
        "user_phone": current_user.phone_number,   # ✅ NEW: Added for debugging
        "user_nickname": current_user.nickname,    # ✅ NEW: Added for debugging
        "message": "Authentication working!"
    }