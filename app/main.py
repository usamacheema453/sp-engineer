from fastapi import FastAPI
from app.routers import user
from app.routers import auth
from app.db.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Include routers
app.include_router(user.router, prefix="/users", tags=["Users"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
