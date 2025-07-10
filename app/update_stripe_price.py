# update_real_stripe_prices.py
import sys
import os
sys.path.append('.')

from app.db.database import SessionLocal
from app.models.subscription import SubscriptionPlan

def update_real_stripe_prices():
    """Update database with real Stripe price IDs"""
    
    # 🔥 REPLACE THESE WITH YOUR ACTUAL STRIPE PRICE IDs
    STRIPE_PRICE_IDS = {
        "solo": {
            "monthly": "price_1RjPsU2NOIKw0xw24zkwC1sp",
            "yearly": "price_1RjPsU2NOIKw0xw2U3ayPrGn"
        },
        "team": {
            "monthly": "price_1RjPtS2NOIKw0xw282QCbhfA", 
            "yearly": "price_1RjPud2NOIKw0xw2lrR4P8i9"
        }
    }
    
    print("🚀 Updating database with real Stripe price IDs...")
    
    db = SessionLocal()
    try:
        # Update Solo plan
        solo_plan = db.query(SubscriptionPlan).filter_by(name="Solo").first()
        if solo_plan:
            solo_plan.stripe_monthly_price_id = STRIPE_PRICE_IDS["solo"]["monthly"]
            solo_plan.stripe_yearly_price_id = STRIPE_PRICE_IDS["solo"]["yearly"]
            print(f"✅ Updated Solo plan")
        else:
            print("❌ Solo plan not found")
        
        # Update Team plan
        team_plan = db.query(SubscriptionPlan).filter_by(name="Team").first()
        if team_plan:
            team_plan.stripe_monthly_price_id = STRIPE_PRICE_IDS["team"]["monthly"]
            team_plan.stripe_yearly_price_id = STRIPE_PRICE_IDS["team"]["yearly"]
            print(f"✅ Updated Team plan")
        else:
            print("❌ Team plan not found")
        
        # Free plan stays null
        free_plan = db.query(SubscriptionPlan).filter_by(name="Free").first()
        if free_plan:
            free_plan.stripe_monthly_price_id = None
            free_plan.stripe_yearly_price_id = None
            print(f"✅ Free plan set to None")
        
        db.commit()
        print("🎉 Database updated successfully!")
        
        # Verify updates
        print("\n📋 Current price IDs:")
        for plan in db.query(SubscriptionPlan).all():
            print(f"{plan.name}:")
            print(f"  Monthly: {plan.stripe_monthly_price_id}")
            print(f"  Yearly: {plan.stripe_yearly_price_id}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_real_stripe_prices()