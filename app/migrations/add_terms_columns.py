# app/migrations/add_terms_columns.py

from sqlalchemy import text
from app.db.database import engine

def add_terms_columns():
    """Add terms acceptance columns to users table"""
    
    migrations = [
        # Add terms_accepted column
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS terms_accepted BOOLEAN DEFAULT FALSE NOT NULL;
        """,
        # Add terms_accepted_at column
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP;
        """,
        # Update existing users to have terms accepted (for backward compatibility)
        """
        UPDATE users 
        SET terms_accepted = TRUE, terms_accepted_at = created_at 
        WHERE terms_accepted = FALSE AND created_at IS NOT NULL;
        """
    ]
    
    with engine.connect() as conn:
        for migration in migrations:
            try:
                conn.execute(text(migration))
                conn.commit()
                print(f"✅ Migration executed successfully")
            except Exception as e:
                print(f"❌ Migration failed: {e}")
                conn.rollback()

if __name__ == "__main__":
    add_terms_columns()
    print("🎉 Terms and conditions migration completed!")