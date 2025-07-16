from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, subscription, webhook  # subscription router is updated
from app.db.database import Base, engine
from app.seed.subscription_seed import seed_subscription_plans  # Updated seed function
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="SuperEngineer API",
    description="Backend API for SuperEngineer mobile app with One-time Payments",
    version="2.0.0"  # Updated version
)

# CORS middleware for React Native
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed subscription plans on startup
@app.on_event("startup")
async def startup_event():
    seed_subscription_plans()  # This will now use the updated seed function

# Include routers - No changes needed!
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(subscription.router, tags=["Subscriptions"])  # Updated router
app.include_router(webhook.router, tags=["Webhooks"])  # Optional for simple method

# Health check endpoint
@app.get("/")
def read_root():
    return {"message": "SuperEngineer API with One-time Payments", "status": "healthy"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "SuperEngineer API v2.0"}