# app/migrate_first_login.py - Add first-time login tracking

import sys
import os
sys.path.append('.')

from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.models.user import User
from datetime import datetime

def add_first_login_tracking():
    """Add first-time login tracking columns"""
    
    print("🚀 Adding first-time login tracking...")
    
    db = SessionLocal()
    
    try:
        # Add new columns to users table
        migration_queries = [
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS first_login_completed BOOLEAN DEFAULT FALSE;
            """,
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;
            """,
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            """
        ]
        
        for query in migration_queries:
            try:
                db.execute(text(query))
                db.commit()
                print(f"✅ Executed: {query.strip()[:50]}...")
            except Exception as e:
                print(f"⚠️ Query might have already been applied: {str(e)[:100]}...")
                db.rollback()
        
        # Update existing users - set first_login_completed to True for users who already have last_login
        print("📋 Updating existing users...")
        
        existing_users = db.query(User).all()
        for user in existing_users:
            if user.last_login is not None:
                # User has logged in before, mark as completed
                user.first_login_completed = True
                user.login_count = 1  # At least one login
            else:
                # New user who hasn't logged in yet
                user.first_login_completed = False
                user.login_count = 0
            
            # Set created_at if not set
            if not hasattr(user, 'created_at') or user.created_at is None:
                user.created_at = datetime.utcnow()
        
        db.commit()
        
        print("✅ First-time login tracking added successfully!")
        print(f"📊 Updated {len(existing_users)} existing users")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_first_login_tracking()