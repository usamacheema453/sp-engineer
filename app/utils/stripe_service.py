# Update your app/utils/stripe_service.py:

import stripe
import os
from app.config import STRIPE_SECRET_KEY

# Initialize Stripe with your secret key
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
        # Return mock ID for development
        return f"cus_mock_{email.replace('@', '_').replace('.', '_')}"

def create_subscription(customer_id: str, price_id: str) -> dict:
    """Create a new Stripe subscription"""
    try:
        if not STRIPE_SECRET_KEY or price_id.startswith('price_mock'):
            print("⚠️ Stripe not configured - using mock subscription")
            return {
                "subscription_id": f"sub_mock_{customer_id}_{price_id}",
                "client_secret": f"pi_mock_{customer_id}_secret"
            }
            
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"]
        )
        
        print(f"✅ Stripe subscription created: {subscription.id}")
        return {
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret
        }
    except Exception as e:
        print(f"❌ Stripe subscription creation failed: {e}")
        # Return mock data for development
        return {
            "subscription_id": f"sub_mock_{customer_id}_{price_id}",
            "client_secret": f"pi_mock_{customer_id}_secret"
        }

def verify_webhook_signature(payload: bytes, signature: str, webhook_secret: str) -> bool:
    """Verify Stripe webhook signature"""
    try:
        stripe.Webhook.construct_event(payload, signature, webhook_secret)
        return True
    except Exception as e:
        print(f"❌ Webhook verification failed: {e}")
        return False

def cancel_subscription(subscription_id: str) -> bool:
    """Cancel a Stripe subscription"""
    try:
        stripe.Subscription.delete(subscription_id)
        return True
    except Exception as e:
        print(f"❌ Error canceling subscription: {e}")
        return False