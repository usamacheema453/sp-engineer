# app/routers/subscription.py - COMPLETE FIXED VERSION

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from app.db.database import get_db
from datetime import datetime, timedelta
from app.models.user import User
from app.models.subscription import SubscriptionPlan, UserSubscription, BillingCycle
import stripe
import os
import logging
from urllib.parse import unquote
import re
from pydantic import BaseModel, EmailStr
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Create router
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

# Request schemas
class CreatePaymentRequest(BaseModel):
    email: EmailStr
    plan_id: int
    billing_cycle: str = "monthly"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

# ✅ Helper function for email decoding
def decode_email(email: str) -> str:
    try:
        decoded = unquote(email)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(email_pattern, decoded):
            return decoded
        return email
    except Exception as e:
        logger.error(f"Error decoding email {email}: {str(e)}")
        return email

# ✅ Helper function for BillingCycle handling
def get_billing_cycle_enum(cycle_str: str):
    """Convert string to BillingCycle enum safely"""
    try:
        if hasattr(BillingCycle, 'monthly') and hasattr(BillingCycle, 'yearly'):
            # If BillingCycle is enum with attributes
            return BillingCycle.yearly if cycle_str == "yearly" else BillingCycle.monthly
        else:
            # If BillingCycle expects string
            return cycle_str
    except Exception as e:
        logger.warning(f"BillingCycle enum issue: {e}, using string: {cycle_str}")
        return cycle_str

# ✅ Helper function for safe BillingCycle value extraction
def get_billing_cycle_value(billing_cycle):
    """Extract billing cycle value safely"""
    try:
        if hasattr(billing_cycle, 'value'):
            return billing_cycle.value
        else:
            return str(billing_cycle)
    except:
        return "monthly"

# ✅ ENHANCED CURRENT SUBSCRIPTION ENDPOINT with better email handling
@router.get("/current/{email}")
def get_current_subscription_enhanced(
    email: str = Path(..., description="User email address"),
    db: Session = Depends(get_db)
):
    """Get current subscription status for user - ENHANCED"""
    try:
        # Decode email properly
        decoded_email = decode_email(email)
        logger.info(f"📋 Getting subscription for: {decoded_email}")
        
        # ✅ ENHANCED: Try multiple email search strategies
        user = None
        
        # Strategy 1: Exact match with decoded email
        user = db.query(User).filter(User.email == decoded_email).first()
        if user:
            logger.info(f"👤 Found user with decoded email: {user.id}")
        
        # Strategy 2: Exact match with original email
        if not user:
            user = db.query(User).filter(User.email == email).first()
            if user:
                logger.info(f"👤 Found user with original email: {user.id}")
        
        # Strategy 3: Partial match (for debugging)
        if not user:
            partial_users = db.query(User).filter(User.email.contains('@gmail.com')).all()
            for potential_user in partial_users:
                if 'osamacheema41' in potential_user.email:
                    logger.info(f"🔍 Found potential user: {potential_user.email}")
        
        if not user:
            logger.info(f"📋 User not found: {decoded_email}")
            
            # ✅ RETURN DEBUG INFO for email mismatch
            all_users = db.query(User).limit(10).all()
            user_emails = [u.email for u in all_users]
            
            return {
                "has_subscription": False,
                "plan": "none",
                "requires_plan_selection": True,
                "message": "User not found",
                "debug_info": {
                    "requested_email": email,
                    "decoded_email": decoded_email,
                    "user_found": False,
                    "similar_emails": [e for e in user_emails if 'osamacheema41' in e],
                    "total_users": len(user_emails)
                }
            }
        
        logger.info(f"👤 Found user: {user.id}")
        
        # Get active subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).first()
        
        logger.info(f"🔍 Subscription query result: {subscription}")
        
        if not subscription:
            # Check if user has ANY subscription (active or inactive)
            any_subscription = db.query(UserSubscription).filter(
                UserSubscription.user_id == user.id
            ).first()
            
            logger.info(f"📋 Any subscription found: {any_subscription}")
            
            return {
                "has_subscription": False,
                "plan": "none", 
                "requires_plan_selection": True,
                "message": "No active subscription found",
                "debug_info": {
                    "user_found": True,
                    "user_id": user.id,
                    "user_email": user.email,  # ✅ SHOW ACTUAL USER EMAIL
                    "requested_email": email,
                    "any_subscription_exists": any_subscription is not None
                }
            }
        
        # Check if subscription is expired
        if subscription.expiry_date and subscription.expiry_date < datetime.utcnow():
            subscription.active = False
            db.commit()
            logger.info(f"📋 Subscription expired for: {decoded_email}")
            return {
                "has_subscription": False,
                "plan": "expired",
                "requires_plan_selection": True, 
                "message": "Subscription expired, please renew"
            }
        
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == subscription.plan_id).first()
        
        logger.info(f"✅ Active subscription found: {plan.name if plan else 'Unknown'}")
        
        return {
            "has_subscription": True,
            "plan": plan.name.lower() if plan else "unknown",
            "plan_display": plan.name if plan else "Unknown",
            "billing_cycle": get_billing_cycle_value(subscription.billing_cycle),
            "expiry_date": subscription.expiry_date.isoformat() if subscription.expiry_date else None,
            "status": "active",
            "requires_plan_selection": False,
            "debug_info": {
                "subscription_id": subscription.id,
                "plan_id": subscription.plan_id,
                "user_id": user.id,
                "user_email": user.email,  # ✅ SHOW ACTUAL USER EMAIL
                "requested_email": email
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting subscription for {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get subscription: {str(e)}")


# ✅ 2. CREATE CHECKOUT SESSION (FIXED)
@router.post("/create-checkout-session")
def create_checkout_session(request: CreatePaymentRequest, db: Session = Depends(get_db)):
    """Create Stripe checkout session"""
    try:
        logger.info(f"🛒 Creating checkout session for {request.email}, plan {request.plan_id}")
        
        # Decode email if needed
        decoded_email = decode_email(request.email)
        
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == request.plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Calculate amount based on billing cycle
        if request.billing_cycle == "yearly":
            amount = plan.yearly_price if plan.yearly_price else 0
            billing_display = "yearly"
        else:
            amount = plan.monthly_price if plan.monthly_price else 0
            billing_display = "monthly"
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid plan pricing")
        
        logger.info(f"💰 Plan: {plan.name}, Amount: {amount} cents, Billing: {billing_display}")
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{plan.name} Plan',
                        'description': f'{plan.name} subscription - {billing_display}',
                    },
                    'unit_amount': int(amount),
                },
                'quantity': 1,
            }],
            mode='payment',
            customer_email=decoded_email,
            metadata={
                'plan_id': str(request.plan_id),
                'billing_cycle': request.billing_cycle,
                'user_email': decoded_email,
            },
            success_url=request.success_url or "http://localhost:8081/payment-success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.cancel_url or "http://localhost:8081/pricing",
        )
        
        logger.info(f"✅ Checkout session created: {checkout_session.id}")
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Payment error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Checkout session error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# ✅ CORRECTED: Activate free plan with proper field names
@router.post("/activate-free")
def activate_free_plan(request: dict, db: Session = Depends(get_db)):
    """Activate free plan for user"""
    try:
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email required")
        
        # Decode email if needed
        decoded_email = decode_email(email)
        logger.info(f"🆓 Activating free plan for: {decoded_email}")
        
        # Find user
        user = db.query(User).filter(User.email == decoded_email).first()
        if not user:
            logger.error(f"❌ User not found: {decoded_email}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"👤 Found user: {user.id}")
        
        # Get free plan (ID = 1)
        free_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == 1).first()
        if not free_plan:
            logger.error("❌ Free plan not found in database")
            raise HTTPException(status_code=404, detail="Free plan not found")
        
        logger.info(f"📋 Found free plan: {free_plan.name}")
        
        # Deactivate existing subscriptions
        existing_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).all()
        
        logger.info(f"🔄 Found {len(existing_subs)} existing active subscriptions")
        
        for sub in existing_subs:
            sub.active = False
            logger.info(f"🔄 Deactivated subscription: {sub.id}")
        
        # ✅ FIXED: Create new free subscription with CORRECT field names
        try:
            billing_cycle = get_billing_cycle_enum("monthly")
            
            free_subscription = UserSubscription(
                user_id=user.id,
                plan_id=1,
                active=True,
                billing_cycle=billing_cycle,
                start_date=datetime.utcnow(),
                expiry_date=datetime.utcnow() + timedelta(days=30),
                next_renewal_date=datetime.utcnow() + timedelta(days=30),
                auto_renew=False,
                queries_used=0,
                documents_uploaded=0,
                last_payment_date=None,  # ✅ CORRECT: last_payment_date
                last_payment_intent_id=None,  # ✅ CORRECT: last_payment_intent_id
                payment_method_id=None,
                renewal_attempts=0,
                renewal_failed=False
            )
            
            logger.info("📝 Created free subscription object with correct fields")
            
            db.add(free_subscription)
            db.commit()
            
            logger.info(f"✅ Free plan activated successfully for: {decoded_email}")
            
            return {
                "success": True,
                "message": "Free plan activated successfully",
                "plan": "free",
                "subscription_id": free_subscription.id,
                "expiry_date": free_subscription.expiry_date.isoformat()
            }
            
        except Exception as model_error:
            logger.error(f"❌ Model creation error: {str(model_error)}")
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Subscription creation failed: {str(model_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error activating free plan: {str(e)}")
        if db:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to activate free plan: {str(e)}")


# app/routers/subscription.py - REMOVE ALL MOCK DATA

@router.get("/payment-status/{session_id}")
def get_payment_status(session_id: str, db: Session = Depends(get_db)):
    """Check payment status for a Stripe checkout session - REAL DATA ONLY"""
    try:
        logger.info(f"🔍 Checking payment status for session: {session_id}")
        
        # ✅ REMOVED: All mock/test session handling
        # No more mock data - only real Stripe sessions
        
        # ✅ Retrieve REAL checkout session from Stripe
        try:
            logger.info(f"📡 Retrieving checkout session from Stripe: {session_id}")
            
            checkout_session = stripe.checkout.Session.retrieve(
                session_id,
                expand=['payment_intent', 'subscription']
            )
            
            logger.info(f"📋 Retrieved session: {checkout_session.id}")
            logger.info(f"📋 Payment status: {checkout_session.payment_status}")
            
        except stripe.error.InvalidRequestError as e:
            logger.error(f"❌ Stripe session not found: {str(e)}")
            raise HTTPException(status_code=404, detail="Payment session not found")
            
        except stripe.error.StripeError as e:
            logger.error(f"❌ Stripe API error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")
        
        # ✅ Map Stripe status to response
        if checkout_session.payment_status == "paid":
            status_response = "succeeded"
        elif checkout_session.payment_status == "unpaid":
            status_response = "pending"
        else:
            status_response = "failed"
        
        # ✅ Extract payment details from REAL Stripe data
        payment_data = {
            "status": status_response,
            "session_id": checkout_session.id,
            "payment_intent": checkout_session.payment_intent.id if checkout_session.payment_intent else None,
            "customer_email": checkout_session.customer_details.email if checkout_session.customer_details else None,
            "amount_total": checkout_session.amount_total,
            "currency": checkout_session.currency,
            "metadata": checkout_session.metadata or {}
        }
        
        # ✅ If payment succeeded, update user subscription with REAL data
        if status_response == "succeeded":
            update_subscription_from_payment(checkout_session, db)
        
        logger.info(f"✅ Payment status response: {payment_data['status']}")
        return payment_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in payment status check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ✅ ALSO UPDATE: Remove mock responses from other functions
def update_subscription_from_payment(checkout_session, db: Session):
    """Update user subscription after successful payment - REAL DATA ONLY"""
    try:
        logger.info("💳 Processing subscription update from payment...")
        
        # ✅ Extract REAL metadata from Stripe
        metadata = checkout_session.metadata or {}
        
        # ✅ Extract REAL email from Stripe checkout session
        user_email = None
        
        # Method 1: From metadata (set during checkout creation)
        if metadata.get('user_email'):
            user_email = metadata.get('user_email')
            logger.info(f"📧 Email from metadata: {user_email}")
        
        # Method 2: From customer_details (Stripe's customer info)
        elif hasattr(checkout_session, 'customer_details') and checkout_session.customer_details:
            if hasattr(checkout_session.customer_details, 'email'):
                user_email = checkout_session.customer_details.email
                logger.info(f"📧 Email from customer_details: {user_email}")
        
        # Method 3: From customer_email field
        elif hasattr(checkout_session, 'customer_email') and checkout_session.customer_email:
            user_email = checkout_session.customer_email
            logger.info(f"📧 Email from customer_email: {user_email}")
        
        # ✅ REMOVED: All mock/fallback email handling
        
        plan_id = metadata.get('plan_id')
        billing_cycle = metadata.get('billing_cycle', 'monthly')
        
        logger.info(f"📋 Extracted data - Email: {user_email}, Plan ID: {plan_id}, Billing: {billing_cycle}")
        
        if not user_email:
            logger.error("❌ No user email found in Stripe session")
            logger.error(f"❌ Available metadata: {metadata}")
            return
        
        if not plan_id:
            logger.error("❌ Missing plan_id in payment metadata")
            logger.error(f"❌ Available metadata: {metadata}")
            return
        
        # ✅ DECODE EMAIL IF NEEDED
        decoded_email = decode_email(user_email)
        logger.info(f"💳 Updating subscription for {decoded_email}, plan {plan_id}")
        
        # Find user in database
        user = db.query(User).filter(User.email == decoded_email).first()
        if not user:
            logger.error(f"❌ User not found: {decoded_email}")
            # Try with original email format
            user = db.query(User).filter(User.email == user_email).first()
            if not user:
                logger.error(f"❌ User not found with either email format")
                return
        
        logger.info(f"👤 Found user: {user.id} - {user.email}")
        
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == int(plan_id)).first()
        if not plan:
            logger.error(f"❌ Plan not found: {plan_id}")
            return
        
        logger.info(f"📋 Found plan: {plan.name}")
        
        # Deactivate existing subscriptions
        existing_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).all()
        
        logger.info(f"🔄 Found {len(existing_subs)} existing active subscriptions to deactivate")
        
        for sub in existing_subs:
            sub.active = False
            logger.info(f"🔄 Deactivated existing subscription: {sub.id}")
        
        # Calculate expiry date
        if billing_cycle == "yearly":
            expiry_date = datetime.utcnow() + timedelta(days=365)
        else:
            expiry_date = datetime.utcnow() + timedelta(days=30)
        
        # Create new subscription with REAL payment data
        billing_cycle_enum = get_billing_cycle_enum(billing_cycle)
        
        # Extract REAL payment intent ID from Stripe
        payment_intent_id = None
        if hasattr(checkout_session, 'payment_intent') and checkout_session.payment_intent:
            if hasattr(checkout_session.payment_intent, 'id'):
                payment_intent_id = checkout_session.payment_intent.id
            else:
                payment_intent_id = str(checkout_session.payment_intent)
        
        logger.info(f"💳 Creating new subscription with payment_intent: {payment_intent_id}")
        
        new_subscription = UserSubscription(
            user_id=user.id,
            plan_id=int(plan_id),
            active=True,
            billing_cycle=billing_cycle_enum,
            start_date=datetime.utcnow(),
            expiry_date=expiry_date,
            next_renewal_date=expiry_date,
            auto_renew=True,
            queries_used=0,
            documents_uploaded=0,
            last_payment_date=datetime.utcnow(),
            last_payment_intent_id=payment_intent_id,
            payment_method_id=None,
            renewal_attempts=0,
            renewal_failed=False
        )
        
        logger.info("📝 Created new subscription object")
        
        db.add(new_subscription)
        db.commit()
        db.refresh(new_subscription)
        
        logger.info(f"✅ Subscription updated successfully for {decoded_email}")
        logger.info(f"✅ New subscription ID: {new_subscription.id}")
        logger.info(f"✅ Plan: {plan.name}, Billing: {billing_cycle}, Expiry: {expiry_date}")
        
        # Verify the update
        verification_sub = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).first()
        
        if verification_sub:
            logger.info(f"✅ VERIFICATION: Active subscription found - Plan ID: {verification_sub.plan_id}")
        else:
            logger.error(f"❌ VERIFICATION FAILED: No active subscription found after update")
        
    except Exception as e:
        logger.error(f"❌ Error updating subscription from payment: {str(e)}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        if db:
            db.rollback()
        raise

# ✅ 6. TEST ENDPOINT
@router.get("/test")
def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "status": "ok",
        "message": "Subscription API is working",
        "timestamp": datetime.utcnow().isoformat(),
        "stripe_configured": bool(stripe.api_key),
        "endpoints": [
            "GET /subscriptions/current/{email}",
            "POST /subscriptions/create-checkout-session", 
            "POST /subscriptions/activate-free",
            "GET /subscriptions/payment-status/{session_id}",
            "GET /subscriptions/test"
        ]
    }

# ✅ 7. DEBUG ENDPOINT
@router.get("/debug/email/{email}")
def debug_email_decoding(email: str):
    """Debug email decoding"""
    try:
        decoded = decode_email(email)
        return {
            "original": email,
            "decoded": decoded,
            "url_encoded": email != decoded,
            "valid_format": bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', decoded))
        }
    except Exception as e:
        return {
            "original": email,
            "error": str(e),
            "status": "failed"
        }

@router.get("/query-status/{email}")
def get_query_status(email: str, db: Session = Depends(get_db)):
    """Get current query usage status for user"""
    try:
        decoded_email = decode_email(email)
        logger.info(f"📊 Getting query status for: {decoded_email}")
        
        # Find user
        user = db.query(User).filter(User.email == decoded_email).first()
        if not user:
            logger.warning(f"❌ User not found: {decoded_email}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get active subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).first()
        
        if not subscription:
            logger.info(f"📊 No active subscription for: {decoded_email}")
            return {
                "has_subscription": False,
                "queries_used": 0,
                "queries_remaining": 0,
                "query_limit": 0,
                "plan": "none"
            }
        
        # Check if subscription expired
        if subscription.expiry_date and subscription.expiry_date < datetime.utcnow():
            subscription.active = False
            db.commit()
            logger.info(f"📊 Subscription expired for: {decoded_email}")
            return {
                "has_subscription": False,
                "queries_used": subscription.queries_used,
                "queries_remaining": 0,
                "query_limit": 0,
                "plan": "expired"
            }
        
        # Get plan details
        plan = subscription.plan
        
        if plan.query_limit <= 0:  # Unlimited plans
            logger.info(f"📊 Unlimited plan for: {decoded_email}")
            return {
                "has_subscription": True,
                "queries_used": subscription.queries_used,
                "queries_remaining": "unlimited",
                "query_limit": "unlimited",
                "plan": plan.name.lower()
            }
        
        # Limited plans
        queries_remaining = max(0, plan.query_limit - subscription.queries_used)
        
        logger.info(f"📊 Query status for {decoded_email}: {subscription.queries_used}/{plan.query_limit}")
        
        return {
            "has_subscription": True,
            "queries_used": subscription.queries_used,
            "queries_remaining": queries_remaining,
            "query_limit": plan.query_limit,
            "plan": plan.name.lower()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting query status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get query status: {str(e)}")

# Add this endpoint in your subscription backend (app/routers/subscription.py)

@router.post("/increment-query")
def increment_query_count(request: dict, db: Session = Depends(get_db)):
    """Increment query count for user - called by chat API"""
    try:
        email = request.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email required")
        
        decoded_email = decode_email(email)
        logger.info(f"📊 Incrementing query count for: {decoded_email}")
        
        # Find user
        user = db.query(User).filter(User.email == decoded_email).first()
        if not user:
            logger.warning(f"❌ User not found: {decoded_email}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Find active subscription
        subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).first()
        
        if not subscription:
            logger.warning(f"❌ No active subscription: {decoded_email}")
            return {
                "success": False,
                "message": "No active subscription found",
                "queries_used": 0
            }
        
        # Check if subscription expired
        if subscription.expiry_date and subscription.expiry_date < datetime.utcnow():
            subscription.active = False
            db.commit()
            logger.info(f"📊 Subscription expired: {decoded_email}")
            return {
                "success": False,
                "message": "Subscription expired",
                "queries_used": subscription.queries_used
            }
        
        # Increment query count
        old_count = subscription.queries_used or 0
        subscription.queries_used = old_count + 1
        db.commit()
        
        logger.info(f"✅ Query count updated: {decoded_email} ({old_count} → {subscription.queries_used})")
        
        return {
            "success": True,
            "message": "Query count updated",
            "queries_used": subscription.queries_used,
            "previous_count": old_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error incrementing query count: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update query count: {str(e)}")        

# ✅ 8. DEBUG SUBSCRIPTION DATABASE
@router.get("/debug/user/{email}")
def debug_user_subscriptions(email: str, db: Session = Depends(get_db)):
    """Debug user subscriptions in database"""
    try:
        decoded_email = decode_email(email)
        
        # Get user
        user = db.query(User).filter(User.email == decoded_email).first()
        if not user:
            return {"error": "User not found", "email": decoded_email}
        
        # Get all subscriptions for user
        all_subs = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).all()
        active_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).all()
        
        subscription_data = []
        for sub in all_subs:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
            subscription_data.append({
                "id": sub.id,
                "plan_id": sub.plan_id,
                "plan_name": plan.name if plan else "Unknown",
                "active": sub.active,
                "billing_cycle": get_billing_cycle_value(sub.billing_cycle),
                "start_date": sub.start_date.isoformat() if sub.start_date else None,
                "expiry_date": sub.expiry_date.isoformat() if sub.expiry_date else None,
                "is_expired": sub.expiry_date < datetime.utcnow() if sub.expiry_date else False
            })
        
        return {
            "user_found": True,
            "user_id": user.id,
            "email": decoded_email,
            "total_subscriptions": len(all_subs),
            "active_subscriptions": len(active_subs),
            "subscriptions": subscription_data
        }
        
    except Exception as e:
        logger.error(f"❌ Debug error: {str(e)}")
        return {"error": str(e), "email": email}

# ✅ CORRECTED: Manual activation with proper field names
@router.post("/manual-activate")
def manual_activate_subscription(request: dict, db: Session = Depends(get_db)):
    """Manually activate subscription for testing"""
    try:
        email = request.get("email")
        plan_id = request.get("plan_id", 2)  # Default to Solo plan
        billing_cycle = request.get("billing_cycle", "monthly")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email required")
        
        decoded_email = decode_email(email)
        logger.info(f"🔧 Manually activating subscription for: {decoded_email}")
        
        # Find user
        user = db.query(User).filter(User.email == decoded_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get plan
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Deactivate existing subscriptions
        existing_subs = db.query(UserSubscription).filter(
            UserSubscription.user_id == user.id,
            UserSubscription.active == True
        ).all()
        
        for sub in existing_subs:
            sub.active = False
        
        # Calculate expiry date
        if billing_cycle == "yearly":
            expiry_date = datetime.utcnow() + timedelta(days=365)
        else:
            expiry_date = datetime.utcnow() + timedelta(days=30)
        
        # ✅ FIXED: Create new subscription with CORRECT field names
        billing_cycle_enum = get_billing_cycle_enum(billing_cycle)
        
        new_subscription = UserSubscription(
            user_id=user.id,
            plan_id=plan_id,
            active=True,
            billing_cycle=billing_cycle_enum,
            start_date=datetime.utcnow(),
            expiry_date=expiry_date,
            next_renewal_date=expiry_date,
            auto_renew=False,  # Manual activation
            queries_used=0,
            documents_uploaded=0,
            last_payment_date=datetime.utcnow(),  # ✅ CORRECT: last_payment_date
            last_payment_intent_id="manual_activation",  # ✅ CORRECT: last_payment_intent_id
            payment_method_id=None,
            renewal_attempts=0,
            renewal_failed=False
        )
        
        db.add(new_subscription)
        db.commit()
        
        logger.info(f"✅ Manual subscription activated for: {decoded_email}")
        
        return {
            "success": True,
            "message": f"{plan.name} plan activated manually",
            "subscription_id": new_subscription.id,
            "plan": plan.name,
            "billing_cycle": billing_cycle,
            "expiry_date": expiry_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error in manual activation: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))