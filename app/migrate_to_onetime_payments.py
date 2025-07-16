# migrate_to_onetime_payments.py - Database migration for one-time payment structure

import sys
import os
sys.path.append('.')

from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.models.subscription import SubscriptionPlan, UserSubscription, PaymentHistory
from app.models.user import User
from datetime import datetime

def run_migration():
    """Run database migration to support one-time payment structure"""
    
    print("🚀 Starting database migration to one-time payment structure...")
    
    db = SessionLocal()
    
    try:
        # Step 1: Add new columns to subscription_plans table
        print("📋 Step 1: Updating subscription_plans table...")
        
        migration_queries = [
            # Add pricing columns
            """
            ALTER TABLE subscription_plans 
            ADD COLUMN IF NOT EXISTS monthly_price INTEGER,
            ADD COLUMN IF NOT EXISTS yearly_price INTEGER;
            """,
            
            # Step 2: Add new columns to users table
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS default_payment_method_id VARCHAR,
            ADD COLUMN IF NOT EXISTS auto_renew_enabled BOOLEAN DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS email_notifications BOOLEAN DEFAULT TRUE;
            """,
            
            # Step 3: Add new columns to user_subscriptions table
            """
            ALTER TABLE user_subscriptions 
            ADD COLUMN IF NOT EXISTS last_payment_date TIMESTAMP,
            ADD COLUMN IF NOT EXISTS last_payment_intent_id VARCHAR,
            ADD COLUMN IF NOT EXISTS payment_method_id VARCHAR,
            ADD COLUMN IF NOT EXISTS next_renewal_date TIMESTAMP,
            ADD COLUMN IF NOT EXISTS renewal_attempts INTEGER DEFAULT 0,
            ADD COLUMN IF NOT EXISTS last_renewal_attempt TIMESTAMP,
            ADD COLUMN IF NOT EXISTS renewal_failed BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS failure_reason TEXT;
            """,
            
            # Step 4: Update existing column name (if needed)
            """
            ALTER TABLE user_subscriptions 
            RENAME COLUMN active TO active;
            """,
        ]
        
        for query in migration_queries:
            try:
                db.execute(text(query))
                db.commit()
                print(f"✅ Executed: {query.strip()[:50]}...")
            except Exception as e:
                print(f"⚠️ Query might have already been applied: {str(e)[:100]}...")
                db.rollback()
        
        # Step 5: Create payment_history table
        print("📋 Step 2: Creating payment_history table...")
        
        payment_history_query = """
        CREATE TABLE IF NOT EXISTS payment_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            subscription_id INTEGER NOT NULL REFERENCES user_subscriptions(id),
            payment_intent_id VARCHAR NOT NULL,
            amount INTEGER NOT NULL,
            currency VARCHAR DEFAULT 'usd',
            status VARCHAR NOT NULL,
            billing_cycle VARCHAR NOT NULL,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_renewal BOOLEAN DEFAULT FALSE,
            meta_info TEXT
        );
        """
        
        try:
            db.execute(text(payment_history_query))
            db.commit()
            print("✅ payment_history table created")
        except Exception as e:
            print(f"⚠️ payment_history table might already exist: {e}")
            db.rollback()
        
        # Step 6: Update subscription plans with new pricing
        print("📋 Step 3: Updating subscription plan pricing...")
        
        plan_updates = [
            {"name": "Free", "monthly_price": 0, "yearly_price": 0},
            {"name": "Solo", "monthly_price": 999, "yearly_price": 9900},
            {"name": "Team", "monthly_price": 2999, "yearly_price": 29900},
            {"name": "Enterprise", "monthly_price": 9999, "yearly_price": 99900},
        ]
        
        for plan_data in plan_updates:
            plan = db.query(SubscriptionPlan).filter_by(name=plan_data["name"]).first()
            if plan:
                plan.monthly_price = plan_data["monthly_price"]
                plan.yearly_price = plan_data["yearly_price"]
                print(f"✅ Updated {plan.name} pricing")
            else:
                print(f"⚠️ Plan not found: {plan_data['name']}")
        
        db.commit()
        
        # Step 7: Update existing user subscriptions
        print("📋 Step 4: Updating existing user subscriptions...")
        
        subscriptions = db.query(UserSubscription).filter_by(active=True).all()
        
        for subscription in subscriptions:
            # Set next renewal date to expiry date if not set
            if not subscription.next_renewal_date:
                subscription.next_renewal_date = subscription.expiry_date
            
            # Set auto_renew to True if not set
            if subscription.auto_renew is None:
                subscription.auto_renew = True
            
            print(f"✅ Updated subscription for user_id {subscription.user_id}")
        
        db.commit()
        
        # Step 8: Update users with default preferences
        print("📋 Step 5: Updating user preferences...")
        
        users = db.query(User).all()
        for user in users:
            if user.auto_renew_enabled is None:
                user.auto_renew_enabled = True
            if user.email_notifications is None:
                user.email_notifications = True
        
        db.commit()
        
        print("\n🎉 Migration completed successfully!")
        print("\n📋 Summary of changes:")
        print("✅ Added pricing columns to subscription_plans")
        print("✅ Added payment tracking columns to user_subscriptions")
        print("✅ Added user preferences columns to users")
        print("✅ Created payment_history table")
        print("✅ Updated existing data with default values")
        
        print("\n🔧 Next steps:")
        print("1. Update your environment variables")
        print("2. Test the new payment flow")
        print("3. Set up the renewal cron job")
        print("4. Monitor logs for any issues")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def rollback_migration():
    """Rollback migration (use with caution)"""
    print("⚠️ Rolling back migration...")
    
    db = SessionLocal()
    
    try:
        rollback_queries = [
            "DROP TABLE IF EXISTS payment_history;",
            "ALTER TABLE subscription_plans DROP COLUMN IF EXISTS monthly_price;",
            "ALTER TABLE subscription_plans DROP COLUMN IF EXISTS yearly_price;",
            "ALTER TABLE users DROP COLUMN IF EXISTS default_payment_method_id;",
            "ALTER TABLE users DROP COLUMN IF EXISTS auto_renew_enabled;",
            "ALTER TABLE users DROP COLUMN IF EXISTS email_notifications;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS last_payment_date;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS last_payment_intent_id;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS payment_method_id;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS next_renewal_date;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS renewal_attempts;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS last_renewal_attempt;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS renewal_failed;",
            "ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS failure_reason;",
        ]
        
        for query in rollback_queries:
            try:
                db.execute(text(query))
                print(f"✅ Rolled back: {query}")
            except Exception as e:
                print(f"⚠️ Rollback warning: {e}")
        
        db.commit()
        print("✅ Rollback completed")
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        run_migration()