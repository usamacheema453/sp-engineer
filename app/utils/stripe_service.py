# app/utils/stripe_service.py - Updated for one-time payments

import stripe
import os
from app.config import STRIPE_SECRET_KEY

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

def create_customer(email: str) -> str:
    """Create a new Stripe customer"""
    try:
        if not STRIPE_SECRET_KEY:
            print("⚠️ Stripe not configured - using mock customer ID")
            return f"cus_mock_{email.replace('@', '_').replace('.', '_')}"
            
        customer = stripe.Customer.create(email=email)
        print(f"✅ Stripe customer created: {customer.id}")
        return customer.id
    except Exception as e:
        print(f"❌ Stripe customer creation failed: {e}")
        return f"cus_mock_{email.replace('@', '_').replace('.', '_')}"

def create_payment_intent(
    customer_id: str, 
    amount: int, 
    plan_name: str,
    billing_cycle: str,
    user_email: str,
    plan_id: int
) -> dict:
    """Create PaymentIntent for one-time payment"""
    try:
        if not STRIPE_SECRET_KEY:
            return {
                "payment_intent_id": f"pi_mock_{customer_id}",
                "client_secret": f"pi_mock_{customer_id}_secret",
                "status": "requires_payment_method"
            }
        
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            customer=customer_id,
            automatic_payment_methods={'enabled': True},
            setup_future_usage='off_session',  # ✅ Save payment method for renewals
            metadata={
                'user_email': user_email,
                'plan_id': str(plan_id),
                'plan_name': plan_name,
                'billing_cycle': billing_cycle,
                'type': 'subscription_payment'
            }
        )
        
        print(f"✅ PaymentIntent created: {payment_intent.id}")
        return {
            "payment_intent_id": payment_intent.id,
            "client_secret": payment_intent.client_secret,
            "status": payment_intent.status
        }
    except Exception as e:
        print(f"❌ PaymentIntent creation failed: {e}")
        return {
            "payment_intent_id": f"pi_mock_{customer_id}",
            "client_secret": f"pi_mock_{customer_id}_secret",
            "status": "requires_payment_method",
            "error": str(e)
        }

def get_payment_intent_details(payment_intent_id: str) -> dict:
    """Get payment intent details from Stripe"""
    try:
        if not STRIPE_SECRET_KEY or payment_intent_id.startswith('pi_mock'):
            return {
                "id": payment_intent_id,
                "status": "succeeded",
                "amount": 999,
                "payment_method": "pm_mock_123",
                "metadata": {}
            }
        
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return {
            "id": payment_intent.id,
            "status": payment_intent.status,
            "amount": payment_intent.amount,
            "payment_method": payment_intent.payment_method,
            "metadata": payment_intent.metadata
        }
    except Exception as e:
        print(f"❌ Error retrieving payment intent: {e}")
        return None

def charge_saved_payment_method(customer_id: str, payment_method_id: str, amount: int, metadata: dict = None) -> dict:
    """Charge saved payment method for renewals"""
    try:
        if not STRIPE_SECRET_KEY:
            return {
                "payment_intent_id": f"pi_renewal_mock_{customer_id}",
                "status": "succeeded",
                "amount": amount
            }
        
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            customer=customer_id,
            payment_method=payment_method_id,
            confirmation_method='automatic',
            confirm=True,
            off_session=True,  # ✅ Indicates automated renewal payment
            metadata=metadata or {}
        )
        
        print(f"✅ Renewal payment successful: {payment_intent.id}")
        return {
            "payment_intent_id": payment_intent.id,
            "status": payment_intent.status,
            "amount": payment_intent.amount
        }
    except stripe.error.CardError as e:
        print(f"❌ Card declined for renewal: {e.user_message}")
        return {
            "error": "card_declined",
            "message": e.user_message,
            "status": "failed"
        }
    except Exception as e:
        print(f"❌ Renewal payment failed: {e}")
        return {
            "error": "payment_failed",
            "message": str(e),
            "status": "failed"
        }

def get_customer_payment_methods(customer_id: str) -> list:
    """Get saved payment methods for customer"""
    try:
        if not STRIPE_SECRET_KEY:
            return []
        
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card"
        )
        return payment_methods.data
    except Exception as e:
        print(f"❌ Error fetching payment methods: {e}")
        return []

def safe_stripe_call(func, *args, **kwargs):
    """Wrapper for safe Stripe API calls"""
    try:
        if not STRIPE_SECRET_KEY:
            logger.warning("Stripe not configured - returning mock response")
            return {"error": "stripe_not_configured"}
        
        return func(*args, **kwargs)
    except stripe.error.CardError as e:
        logger.error(f"Card error: {e.user_message}")
        return {"error": "card_error", "message": e.user_message}
    except stripe.error.RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        return {"error": "rate_limit", "message": "Too many requests"}
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Invalid request: {e}")
        return {"error": "invalid_request", "message": str(e)}
    except stripe.error.AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"error": "authentication", "message": "Invalid API key"}
    except stripe.error.APIConnectionError as e:
        logger.error(f"Network error: {e}")
        return {"error": "network", "message": "Network error"}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return {"error": "stripe_error", "message": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": "unexpected", "message": str(e)}
