# app/main.py - Fixed router registration

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(title="SuperEngineer API", version="1.0.0")

# ✅ CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
# ✅ IMPORT ALL MODELS FIRST (IMPORTANT!)
try:
    from app.models import user, user_settings, subscription, blacklist
    print("✅ All models imported successfully")
except Exception as e:
    print(f"❌ Model import error: {e}")

# ✅ REGISTER ROUTERS
try:
    from app.routers.user_settings import router as user_settings_router
    app.include_router(user_settings_router)
    print("✅ User Settings router registered successfully")
except Exception as e:
    print(f"❌ User Settings router error: {e}")

try:
    from app.routers.auth import router as auth_router
    app.include_router(auth_router, prefix="/auth")
    print("✅ Auth router registered successfully")
except Exception as e:
    print(f"❌ Auth router error: {e}")

try:
    from app.routers.subscription import router as subscription_router
    app.include_router(subscription_router)
    print("✅ Subscription router registered successfully")
except Exception as e:
    print(f"❌ Subscription router error: {e}")

try:
    from app.routers.payment_methods import router as payment_methods_router
    app.include_router(payment_methods_router)
    print("✅ Payment Methods router registered successfully")
except Exception as e:
    print(f"❌ Payment Methods router error: {e}")

try:
    from app.routers.webhook_enhanced import router as webhook_enhanced_router
    app.include_router(webhook_enhanced_router)
    print("✅ Webhook Enhanced router registered successfully")
except Exception as e:
    print(f"❌ Webhook Enhanced router error: {e}")

try:
    from app.routers.subscription_cancellation import router as cancellation_router
    app.include_router(cancellation_router)
    print("✅ Subscription Cancellation router registered successfully")
except Exception as e:
    print(f"❌ Subscription Cancellation router error: {e}")


@app.get("/")
async def root():
    return {"message": "SuperEngineer API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is working"}


# ✅ Debug: List all registered routes
@app.get("/debug/routes")
async def debug_routes():
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', 'unnamed')
            })
    return {"routes": routes}

# ✅ NEW: Payment Method Status Check
@app.get("/debug/payment-methods-status")
async def payment_methods_status():
    """Debug endpoint to check payment methods functionality"""
    try:
        import stripe
        from app.config import STRIPE_SECRET_KEY
        
        stripe.api_key = STRIPE_SECRET_KEY
        
        # Test Stripe connection
        try:
            stripe.Account.retrieve()
            stripe_status = "connected"
        except Exception as e:
            stripe_status = f"error: {str(e)}"
        
        return {
            "payment_methods_enabled": True,
            "stripe_configured": bool(STRIPE_SECRET_KEY),
            "stripe_status": stripe_status,
            "available_endpoints": {
                "get_payment_methods": "GET /payment-methods/",
                "setup_payment_method": "POST /payment-methods/setup-intent",
                "confirm_setup": "POST /payment-methods/confirm-setup/{setup_intent_id}",
                "set_default": "POST /payment-methods/set-default/{payment_method_id}",
                "delete_method": "DELETE /payment-methods/{payment_method_id}",
                "charge_saved": "POST /payment-methods/charge-saved",
                "enhanced_checkout": "POST /payment-methods/enhanced-checkout"
            }
        }
    except Exception as e:
        return {
            "payment_methods_enabled": False,
            "error": str(e)
        }



# CORS preflight handler
@app.options("/{path:path}")
async def options_handler():
    return {"message": "CORS preflight successful"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)