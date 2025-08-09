
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.subscription import UserSubscription, SubscriptionPlan, SubscriptionCancellation, CancellationReason
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscription", tags=["Subscription Cancellation"])

# ✅ REQUEST SCHEMAS
class CancelSubscriptionRequest(BaseModel):
    reason: str = "user_request"  # user_request, too_expensive, not_using, found_alternative, other
    feedback: Optional[str] = None
    immediate_cancellation: bool = False  # For admin/emergency cancellations

class CancelSubscriptionResponse(BaseModel):
    success: bool
    message: str
    subscription_id: int
    cancelled_at: str
    access_until: str
    remaining_days: int
    plan_name: str
    will_auto_renew: bool
    cancellation_id: int

@router.post("/cancel", response_model=CancelSubscriptionResponse)
def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None  # ✅ Make it optional
):
    """Cancel user's subscription (maintains access until period ends)"""
    try:
        logger.info(f"🚫 Cancellation request from user {current_user.id}: {current_user.email}")
        
        # Get active subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.active == True
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="No active subscription found to cancel"
            )
        
        # Check if already cancelled
        if subscription.is_cancelled:
            raise HTTPException(
                status_code=400,
                detail="Subscription is already cancelled"
            )
        
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription.plan_id
        ).first()
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Calculate remaining days
        now = datetime.utcnow()
        access_until = subscription.expiry_date
        remaining_days = max(0, (access_until - now).days)
        
        logger.info(f"📊 Subscription details: Plan: {plan.name}, Expires: {access_until}, Remaining: {remaining_days} days")
        
        # Map user-friendly reason to enum
        reason_mapping = {
            "user_request": CancellationReason.user_request,
            "too_expensive": CancellationReason.user_request,
            "not_using": CancellationReason.user_request,
            "found_alternative": CancellationReason.user_request,
            "other": CancellationReason.other
        }
        
        cancellation_reason = reason_mapping.get(request.reason, CancellationReason.user_request)
        
        # ✅ Update subscription (CANCEL but keep access until expiry)
        subscription.is_cancelled = True
        subscription.cancelled_at = now
        subscription.cancellation_reason = cancellation_reason
        subscription.cancellation_note = request.feedback
        subscription.cancelled_by_user_id = current_user.id
        subscription.auto_renew = False  # Disable auto-renewal
        subscription.access_ends_at = access_until  # Access until current period ends
        
        # For immediate cancellation (admin only)
        if request.immediate_cancellation:
            subscription.active = False
            subscription.access_ends_at = now
            access_until = now
            remaining_days = 0
        
        # ✅ FIXED: Safe IP and User Agent extraction
        ip_address = None
        user_agent = None
        
        if http_request:
            try:
                # ✅ Safe way to get IP address
                if hasattr(http_request, 'client') and http_request.client:
                    ip_address = http_request.client.host
                elif hasattr(http_request, 'headers'):
                    # Try to get from X-Forwarded-For header
                    forwarded_for = http_request.headers.get('X-Forwarded-For')
                    if forwarded_for:
                        ip_address = forwarded_for.split(',')[0].strip()
                    else:
                        ip_address = http_request.headers.get('X-Real-IP', 'unknown')
                
                # ✅ Safe way to get User Agent
                if hasattr(http_request, 'headers'):
                    user_agent = http_request.headers.get('user-agent', 'unknown')
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not extract request info: {e}")
                ip_address = 'unknown'
                user_agent = 'unknown'
        
        # ✅ Create cancellation record
        cancellation_record = SubscriptionCancellation(
            subscription_id=subscription.id,
            user_id=current_user.id,
            cancelled_at=now,
            reason=cancellation_reason,
            user_feedback=request.feedback,
            plan_name=plan.name,
            billing_cycle=subscription.billing_cycle.value,
            remaining_days=remaining_days,
            access_until=access_until,
            prorated_refund_amount=0,  # No refunds for now
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(cancellation_record)
        db.commit()
        db.refresh(cancellation_record)
        
        logger.info(f"✅ Subscription cancelled successfully: {subscription.id}")
        
        # Send cancellation email
        try:
            send_cancellation_confirmation_email(current_user, plan, subscription, remaining_days, access_until)
        except Exception as e:
            logger.error(f"❌ Failed to send cancellation email: {e}")
        
        return CancelSubscriptionResponse(
            success=True,
            message=f"Subscription cancelled. You'll retain access until {access_until.strftime('%B %d, %Y')}",
            subscription_id=subscription.id,
            cancelled_at=now.isoformat(),
            access_until=access_until.isoformat(),
            remaining_days=remaining_days,
            plan_name=plan.name,
            will_auto_renew=False,
            cancellation_id=cancellation_record.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error cancelling subscription: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel subscription: {str(e)}"
        )
 

# ✅ 2. GET CANCELLATION STATUS
@router.get("/cancellation-status")
def get_cancellation_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current subscription cancellation status"""
    try:
        # Get active subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.active == True
        ).first()
        
        if not subscription:
            return {
                "has_subscription": False,
                "message": "No active subscription found"
            }
        
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription.plan_id
        ).first()
        
        # Calculate status
        now = datetime.utcnow()
        remaining_days = max(0, (subscription.expiry_date - now).days)
        
        if subscription.is_cancelled:
            # Get cancellation details
            cancellation = db.query(SubscriptionCancellation).filter(
                SubscriptionCancellation.subscription_id == subscription.id
            ).first()
            
            return {
                "has_subscription": True,
                "is_cancelled": True,
                "plan_name": plan.name if plan else "Unknown",
                "cancelled_at": subscription.cancelled_at.isoformat(),
                "access_until": subscription.expiry_date.isoformat(),
                "remaining_days": remaining_days,
                "will_auto_renew": False,
                "cancellation_reason": subscription.cancellation_reason.value if subscription.cancellation_reason else None,
                "user_feedback": cancellation.user_feedback if cancellation else None,
                "message": f"Subscription cancelled. Access until {subscription.expiry_date.strftime('%B %d, %Y')}"
            }
        else:
            return {
                "has_subscription": True,
                "is_cancelled": False,
                "plan_name": plan.name if plan else "Unknown",
                "expiry_date": subscription.expiry_date.isoformat(),
                "remaining_days": remaining_days,
                "will_auto_renew": subscription.auto_renew,
                "message": "Subscription is active"
            }
            
    except Exception as e:
        logger.error(f"❌ Error getting cancellation status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cancellation status: {str(e)}"
        )

# ✅ 3. REACTIVATE SUBSCRIPTION (if not expired)
@router.post("/reactivate")
def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reactivate a cancelled subscription (only if not expired)"""
    try:
        # Get cancelled subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.active == True,
            UserSubscription.is_cancelled == True
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail="No cancelled subscription found to reactivate"
            )
        
        # Check if still within access period
        now = datetime.utcnow()
        if now > subscription.expiry_date:
            raise HTTPException(
                status_code=400,
                detail="Subscription has expired and cannot be reactivated. Please purchase a new subscription."
            )
        
        # Reactivate subscription
        subscription.is_cancelled = False
        subscription.cancelled_at = None
        subscription.cancellation_reason = None
        subscription.cancellation_note = None
        subscription.auto_renew = True  # Re-enable auto-renewal
        subscription.access_ends_at = None
        
        db.commit()
        
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.id == subscription.plan_id
        ).first()
        
        logger.info(f"✅ Subscription reactivated: {subscription.id} for user {current_user.email}")
        
        return {
            "success": True,
            "message": f"{plan.name} subscription reactivated successfully!",
            "plan_name": plan.name if plan else "Unknown",
            "expiry_date": subscription.expiry_date.isoformat(),
            "will_auto_renew": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error reactivating subscription: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reactivate subscription: {str(e)}"
        )

# ✅ 4. GET CANCELLATION HISTORY
@router.get("/cancellation-history")
def get_cancellation_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's subscription cancellation history"""
    try:
        cancellations = db.query(SubscriptionCancellation).filter(
            SubscriptionCancellation.user_id == current_user.id
        ).order_by(SubscriptionCancellation.cancelled_at.desc()).all()
        
        history = []
        for cancellation in cancellations:
            history.append({
                "cancellation_id": cancellation.id,
                "plan_name": cancellation.plan_name,
                "billing_cycle": cancellation.billing_cycle,
                "cancelled_at": cancellation.cancelled_at.isoformat(),
                "reason": cancellation.reason.value,
                "user_feedback": cancellation.user_feedback,
                "access_until": cancellation.access_until.isoformat(),
                "remaining_days_at_cancellation": cancellation.remaining_days
            })
        
        return {
            "success": True,
            "total_cancellations": len(history),
            "cancellation_history": history
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting cancellation history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cancellation history: {str(e)}"
        )

# ✅ EMAIL NOTIFICATION FUNCTION
def send_cancellation_confirmation_email(user: User, plan: SubscriptionPlan, subscription: UserSubscription, remaining_days: int, access_until: datetime):
    """Send cancellation confirmation email"""
    from app.utils.email import send_email
    
    if not user.email_notifications:
        logger.info(f"📧 Skipping cancellation email (user preference): {user.email}")
        return
    
    subject = f"✅ Subscription Cancelled - {plan.name} Plan"
    
    body = f"""
Hi {user.full_name},

Your {plan.name} subscription has been successfully cancelled.

📋 Cancellation Details:
• Plan: {plan.name}
• Cancelled on: {subscription.cancelled_at.strftime('%B %d, %Y at %I:%M %p')}
• Access until: {access_until.strftime('%B %d, %Y')}
• Remaining days: {remaining_days} days

🔄 What happens next:
• You'll retain full access to all {plan.name} features until {access_until.strftime('%B %d, %Y')}
• Your subscription will NOT auto-renew
• No further charges will be made
• You can reactivate anytime before {access_until.strftime('%B %d, %Y')}

💡 Need to come back?
You can reactivate your subscription anytime through your account settings before your access expires.

We're sorry to see you go! If you have any feedback on how we can improve, please reply to this email.

Best regards,
The SuperEngineer Team

---
Need help? Contact us at support@superengineer.com
    """
    
    try:
        send_email(user.email, subject, body)
        logger.info(f"📧 Cancellation confirmation email sent to {user.email}")
    except Exception as e:
        logger.error(f"❌ Failed to send cancellation email to {user.email}: {e}")
