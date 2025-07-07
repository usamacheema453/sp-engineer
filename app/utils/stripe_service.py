import stripe
from app.config import STRIPE_SECRET_KEY

stripe.api_key = STRIPE_SECRET_KEY

def create_customer(email: str) -> str:
    cust = stripe.Customer.create(email=email)
    return cust.id

def create_subscription(customer_id: str, price_id: str) -> dict:
    sub = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"]
    )
    return {
        "subscription_id": sub.id,
        "client_secret": sub.latest_invoice.payment_intent.client_secret
    }
