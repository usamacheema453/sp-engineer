from fastapi import FastAPI
from app.routers import user
from app.routers import auth
from app.db.database import Base, engine
from app.seed.subscription_seed import seed_subscription_plans
from app.routers import subscription
from app.routers import webhook
from dotenv import load_dotenv

Base.metadata.create_all(bind=engine)
load_dotenv()
app = FastAPI()

# Include routers
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
seed_subscription_plans()  # Call after DB setup
app.include_router(subscription.router)
app.include_router(webhook.router)