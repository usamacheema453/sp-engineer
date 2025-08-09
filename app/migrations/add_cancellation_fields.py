
from sqlalchemy import text
from app.db.database import engine

def add_cancellation_fields():
    """Add cancellation fields to existing subscription table"""
    
    migrations = [
        # Add cancellation fields to user_subscriptions
        """
        ALTER TABLE user_subscriptions 
        ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN DEFAULT FALSE;
        """,
        """
        ALTER TABLE user_subscriptions 
        ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP;
        """,
        """
        ALTER TABLE user_subscriptions 
        ADD COLUMN IF NOT EXISTS cancellation_note TEXT;
        """,
        """
        ALTER TABLE user_subscriptions 
        ADD COLUMN IF NOT EXISTS cancelled_by_user_id INTEGER;
        """,
        """
        ALTER TABLE user_subscriptions 
        ADD COLUMN IF NOT EXISTS access_ends_at TIMESTAMP;
        """,
        # Create cancellation_reason enum
        """
        DO $$ BEGIN
            CREATE TYPE cancellationreason AS ENUM ('user_request', 'payment_failed', 'admin_action', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """,
        """
        ALTER TABLE user_subscriptions 
        ADD COLUMN IF NOT EXISTS cancellation_reason cancellationreason;
        """,
        # Create subscription_cancellations table
        """
        CREATE TABLE IF NOT EXISTS subscription_cancellations (
            id SERIAL PRIMARY KEY,
            subscription_id INTEGER REFERENCES user_subscriptions(id),
            user_id INTEGER REFERENCES users(id),
            cancelled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason cancellationreason NOT NULL,
            user_feedback TEXT,
            plan_name VARCHAR NOT NULL,
            billing_cycle VARCHAR NOT NULL,
            remaining_days INTEGER,
            access_until TIMESTAMP NOT NULL,
            prorated_refund_amount INTEGER DEFAULT 0,
            refund_processed BOOLEAN DEFAULT FALSE,
            refund_transaction_id VARCHAR,
            ip_address VARCHAR,
            user_agent VARCHAR
        );
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
    add_cancellation_fields()
    print("🎉 Cancellation feature database migration completed!")
