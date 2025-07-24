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
    allow_origins=[
        "http://localhost:8081",
        "http://localhost:3000", 
        "http://127.0.0.1:8081",
        "https://yourapp.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ✅ Import and register routers
try:
    from app.routers.subscription import router as subscription_router
    
    # Register subscription router
    app.include_router(subscription_router)
    print("✅ Subscription router registered successfully")
    
except ImportError as e:
    print(f"❌ Failed to import subscription router: {e}")
    
    # ✅ Fallback: Create basic endpoints directly in main.py
    @app.get("/subscriptions/test")
    def fallback_test():
        return {"status": "fallback", "message": "Direct endpoint working"}

try:
    from app.routers.auth import router as auth_router
    app.include_router(auth_router, prefix="/auth")
    print("✅ Auth router registered successfully")
except ImportError as e:
    print(f"⚠️ Auth router not found: {e}")

# Health check endpoints
@app.get("/")
async def root():
    return {
        "message": "SuperEngineer API is running", 
        "status": "healthy",
        "cors_enabled": True
    }

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "API is working",
        "cors_enabled": True,
        "timestamp": "2025-01-28",
        "registered_routes": len(app.routes)
    }

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

# CORS preflight handler
@app.options("/{path:path}")
async def options_handler():
    return {"message": "CORS preflight successful"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)