from sqlalchemy.orm import Session
from app import models, schemas

def create_user(db: Session, user: schemas.user.UserCreate):
    db_user = models.user.User(name=user.name, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session):
    return db.query(models.user.User).all()
