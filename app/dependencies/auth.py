from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.utils.token import decode_token, is_token_blacklisted
from sqlalchemy.orm import Session
from app.db.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if is_token_blacklisted(token, db):
        raise HTTPException(status_code=401, detail="Token is blacklisted. Please login again.")

    payload = decode_token(token)  # your existing decode method
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user
