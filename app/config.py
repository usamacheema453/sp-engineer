# app/config.py - Updated for simple method

import os
from dotenv import load_dotenv

load_dotenv()

# ✅ Required Stripe keys
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# ✅ Optional - only needed if you want to use webhooks later
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")  # Optional for simple method