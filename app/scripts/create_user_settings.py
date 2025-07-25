# app/scripts/create_user_settings.py
from sqlalchemy import create_engine
from app.db.database import DATABASE_URL
from app.models.user import User  # ✅ User model import karo
from app.models.user_settings import UserSettings

def create_user_settings_table():
    try:
        engine = create_engine(DATABASE_URL)
        
        # ✅ Import all models pehle
        from app.models import user, user_settings
        
        UserSettings.__table__.create(engine, checkfirst=True)
        print("✅ user_settings table successfully create ho gaya!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    create_user_settings_table()