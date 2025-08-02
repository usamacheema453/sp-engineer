# app/routers/payment_methods.py - Real Payment Method Management

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.subscription import UserSubscription, SubscriptionPlan, BillingCycle, PaymentHistory
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import stripe
import logging
from app.config import STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)
stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/payment-methods", tags=["Payment Methods"])

# ✅ RESPONSE SCHEMAS
class PaymentMethodResponse(BaseModel):
    id: str
    type: str
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    is_default: bool = False
    created: datetime

class ChargeRequest(BaseModel):
    plan_id: int
    billing_cycle: str = "monthly"
    payment_method_id: Optional[str] = None

# ✅ 1. GET USER'S SAVED PAYMENT METHODS
@router.get("/", response_model=List[PaymentMethodResponse])
def get_saved_payment_methods(
    current_user: User = Depends(get_current_user)
):
    """Get all saved payment methods for current user"""
    try:
        if not current_user.stripe_customer_id:
            return []
        
        # Get payment methods from Stripe
        payment_methods = stripe.PaymentMethod.list(
            customer=current_user.stripe_customer_id,
            type="card"
        )
        
        methods_response = []
        for pm in payment_methods.data:
            is_default = (pm.id == current_user.default_payment_method_id)
            
            method_data = {
                "id": pm.id,
                "type": pm.type,
                "is_default": is_default,
                "created": datetime.fromtimestamp(pm.created)
            }
            
            # Add card details
            if pm.type == "card" and pm.card:
                method_data.update({
                    "card_brand": pm.card.brand.upper(),
                    "card_last4": pm.card.last4,
                    "card_exp_month": pm.card.exp_month,
                    "card_exp_year": pm.card.exp_year
                })
            
            methods_response.append(PaymentMethodResponse(**method_data))
        
        logger.info(f"✅ Retrieved {len(methods_response)} payment methods for user {current_user.id}")
        return methods_response
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error fetching payment methods: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch payment methods")

# ✅ 2. CREATE SETUP INTENT (Save Payment Method Without Charging)
@router.post("/setup-intent")
def create_setup_intent_for_saving(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create setup intent to save payment method without charging"""
    try:
        # Ensure user has Stripe customer ID
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': str(current_user.id)}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
            logger.info(f"✅ Created Stripe customer: {customer.id}")
        
        # Create SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            usage='off_session',  # For future payments
            metadata={
                'user_id': str(current_user.id),
                'purpose': 'save_payment_method'
            }
        )
        
        logger.info(f"✅ SetupIntent created: {setup_intent.id}")
        
        return {
            "setup_intent_id": setup_intent.id,
            "client_secret": setup_intent.client_secret,
            "customer_id": current_user.stripe_customer_id
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error creating setup intent: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error creating setup intent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create setup intent")

# ✅ 3. CONFIRM SETUP INTENT (After frontend completes card saving)
@router.post("/confirm-setup/{setup_intent_id}")
def confirm_setup_intent(
    setup_intent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm that payment method was saved successfully"""
    try:
        # Retrieve SetupIntent from Stripe
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        
        if setup_intent.status != "succeeded":
            raise HTTPException(
                status_code=400, 
                detail=f"Setup not completed. Status: {setup_intent.status}"
            )
        
        payment_method_id = setup_intent.payment_method
        
        # Set as default if user doesn't have one
        if not current_user.default_payment_method_id:
            current_user.default_payment_method_id = payment_method_id
            db.commit()
            
            logger.info(f"✅ Payment method saved and set as default: {payment_method_id}")
            return {
                "success": True,
                "payment_method_id": payment_method_id,
                "is_default": True,
                "message": "Payment method saved and set as default"
            }
        
        logger.info(f"✅ Payment method saved: {payment_method_id}")
        return {
            "success": True,
            "payment_method_id": payment_method_id,
            "is_default": False,
            "message": "Payment method saved successfully"
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error confirming setup: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error confirming setup intent: {e}")
        raise HTTPException(status_code=500, detail="Failed to confirm payment method setup")

# ✅ 4. SET DEFAULT PAYMENT METHOD
@router.post("/set-default/{payment_method_id}")
def set_default_payment_method(
    payment_method_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a payment method as default"""
    try:
        # Verify payment method belongs to user
        payment_methods = stripe.PaymentMethod.list(
            customer=current_user.stripe_customer_id,
            type="card"
        )
        
        pm_ids = [pm.id for pm in payment_methods.data]
        if payment_method_id not in pm_ids:
            raise HTTPException(
                status_code=404, 
                detail="Payment method not found"
            )
        
        # Update in database
        current_user.default_payment_method_id = payment_method_id
        db.commit()
        
        logger.info(f"✅ Default payment method updated: {payment_method_id}")
        return {
            "success": True,
            "default_payment_method_id": payment_method_id,
            "message": "Default payment method updated"
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error setting default payment method: {e}")
        raise HTTPException(status_code=500, detail="Failed to set default payment method")

# ✅ 5. DELETE PAYMENT METHOD
@router.delete("/{payment_method_id}")
def delete_payment_method(
    payment_method_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a saved payment method"""
    try:
        # Verify ownership
        payment_methods = stripe.PaymentMethod.list(
            customer=current_user.stripe_customer_id,
            type="card"
        )
        
        pm_ids = [pm.id for pm in payment_methods.data]
        if payment_method_id not in pm_ids:
            raise HTTPException(status_code=404, detail="Payment method not found")
        
        # Check if user has active auto-renewing subscription
        active_subscription = db.query(UserSubscription).filter(
            UserSubscription.user_id == current_user.id,
            UserSubscription.active == True,
            UserSubscription.auto_renew == True
        ).first()
        
        if active_subscription and len(pm_ids) == 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the only payment method with active auto-renewing subscription"
            )
        
        # Detach from Stripe
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        payment_method.detach()
        
        # Update default if this was the default
        if current_user.default_payment_method_id == payment_method_id:
            remaining_methods = [pm for pm in payment_methods.data if pm.id != payment_method_id]
            if remaining_methods:
                current_user.default_payment_method_id = remaining_methods[0].id
            else:
                current_user.default_payment_method_id = None
            db.commit()
        
        logger.info(f"✅ Payment method deleted: {payment_method_id}")
        return {
            "success": True,
            "message": "Payment method deleted successfully"
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error deleting payment method: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete payment method")

# ✅ 6. CHARGE SAVED PAYMENT METHOD
@router.post("/charge-saved")
def charge_saved_payment_method(
    request: ChargeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Charge a previously saved payment method"""
    try:
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == request.plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Determine payment method to use
        payment_method_id = request.payment_method_id or current_user.default_payment_method_id
        
        if not payment_method_id:
            raise HTTPException(
                status_code=400,
                detail="No payment method available. Please save a payment method first."
            )
        
        # Verify payment method belongs to user
        payment_methods = stripe.PaymentMethod.list(
            customer=current_user.stripe_customer_id,
            type="card"
        )
        pm_ids = [pm.id for pm in payment_methods.data]
        
        if payment_method_id not in pm_ids:
            raise HTTPException(status_code=404, detail="Payment method not found")
        
        # Calculate amount
        if request.billing_cycle == "yearly":
            amount = plan.yearly_price
        else:
            amount = plan.monthly_price
        
        if not amount:
            raise HTTPException(status_code=400, detail="Plan pricing not configured")
        
        # Create PaymentIntent with saved payment method
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            customer=current_user.stripe_customer_id,
            payment_method=payment_method_id,
            confirmation_method='automatic',
            confirm=True,
            off_session=True,  # This indicates it's an automated payment
            metadata={
                'user_id': str(current_user.id),
                'plan_id': str(request.plan_id),
                'plan_name': plan.name,
                'billing_cycle': request.billing_cycle,
                'type': 'saved_payment_method_charge'
            }
        )
        
        if payment_intent.status != 'succeeded':
            raise HTTPException(
                status_code=400,
                detail=f"Payment failed with status: {payment_intent.status}"
            )
        
        # Create/update subscription
        subscription = create_or_update_subscription(
            user=current_user,
            plan=plan,
            billing_cycle=request.billing_cycle,
            payment_intent_id=payment_intent.id,
            payment_method_id=payment_method_id,
            db=db
        )
        
        # Create payment history
        create_payment_history_record(
            user_id=current_user.id,
            subscription_id=subscription.id,
            payment_intent_id=payment_intent.id,
            amount=amount,
            billing_cycle=request.billing_cycle,
            db=db
        )
        
        logger.info(f"✅ Saved payment method charged successfully: {payment_intent.id}")
        
        return {
            "success": True,
            "payment_intent_id": payment_intent.id,
            "subscription_id": subscription.id,
            "plan_name": plan.name,
            "billing_cycle": request.billing_cycle,
            "amount_paid": amount / 100,
            "payment_method_last4": payment_method_id[-4:],
            "message": f"{plan.name} plan activated successfully!"
        }
        
    except stripe.error.CardError as e:
        logger.error(f"❌ Card declined: {e.user_message}")
        raise HTTPException(status_code=400, detail=f"Card declined: {e.user_message}")
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error charging saved payment method: {e}")
        raise HTTPException(status_code=500, detail="Payment processing failed")

# ✅ 7. ENHANCED CHECKOUT WITH PAYMENT METHOD SAVING
@router.post("/enhanced-checkout")
def create_enhanced_checkout_session(
    plan_id: int,
    billing_cycle: str = "monthly",
    save_payment_method: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create checkout session that ALSO saves payment method
    This extends your existing checkout functionality
    """
    try:
        # Get plan details
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Ensure user has Stripe customer ID
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={'user_id': str(current_user.id)}
            )
            current_user.stripe_customer_id = customer.id
            db.commit()
        
        # Calculate amount
        if billing_cycle == "yearly":
            amount = plan.yearly_price
        else:
            amount = plan.monthly_price
        
        if not amount:
            raise HTTPException(status_code=400, detail="Plan pricing not configured")
        
        # Create checkout session with payment method saving
        checkout_session_data = {
            'payment_method_types': ['card'],
            'line_items': [{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{plan.name} Plan',
                        'description': f'{plan.name} subscription - {billing_cycle}',
                    },
                    'unit_amount': int(amount),
                },
                'quantity': 1,
            }],
            'mode': 'payment',
            'customer': current_user.stripe_customer_id,
            'metadata': {
                'plan_id': str(plan_id),
                'billing_cycle': billing_cycle,
                'user_email': current_user.email,
                'user_id': str(current_user.id),
                'save_payment_method': str(save_payment_method)
            },
            'success_url': "http://localhost:8081/payment-success?session_id={CHECKOUT_SESSION_ID}",
            'cancel_url': "http://localhost:8081/pricing",
        }
        
        # Add payment method saving if requested
        if save_payment_method:
            checkout_session_data['payment_intent_data'] = {
                'setup_future_usage': 'off_session'
            }
        
        checkout_session = stripe.checkout.Session.create(**checkout_session_data)
        
        logger.info(f"✅ Enhanced checkout session created: {checkout_session.id}")
        
        return {
            "success": True,
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "will_save_payment_method": save_payment_method
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"❌ Stripe error: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {e.user_message}")
    except Exception as e:
        logger.error(f"❌ Error creating enhanced checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

# ✅ HELPER FUNCTIONS
def create_or_update_subscription(
    user: User,
    plan: SubscriptionPlan,
    billing_cycle: str,
    payment_intent_id: str,
    payment_method_id: str,
    db: Session
) -> UserSubscription:
    """Create or update user subscription"""
    
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
    
    # Create new subscription
    billing_cycle_enum = BillingCycle.yearly if billing_cycle == "yearly" else BillingCycle.monthly
    
    new_subscription = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        active=True,
        billing_cycle=billing_cycle_enum,
        start_date=datetime.utcnow(),
        expiry_date=expiry_date,
        next_renewal_date=expiry_date,
        auto_renew=True,  # Enable auto-renewal since payment method is saved
        queries_used=0,
        documents_uploaded=0,
        last_payment_date=datetime.utcnow(),
        last_payment_intent_id=payment_intent_id,
        payment_method_id=payment_method_id,
        renewal_attempts=0,
        renewal_failed=False
    )
    
    db.add(new_subscription)
    
    # Update user's default payment method if they don't have one
    if not user.default_payment_method_id:
        user.default_payment_method_id = payment_method_id
    
    db.commit()
    db.refresh(new_subscription)
    
    return new_subscription

def create_payment_history_record(
    user_id: int,
    subscription_id: int,
    payment_intent_id: str,
    amount: int,
    billing_cycle: str,
    db: Session
):
    """Create payment history record"""
    billing_cycle_enum = BillingCycle.yearly if billing_cycle == "yearly" else BillingCycle.monthly
    
    payment_record = PaymentHistory(
        user_id=user_id,
        subscription_id=subscription_id,
        payment_intent_id=payment_intent_id,
        amount=amount,
        currency='usd',
        status='succeeded',
        billing_cycle=billing_cycle_enum,
        payment_date=datetime.utcnow(),
        is_renewal=False
    )
    
    db.add(payment_record)
    db.commit()