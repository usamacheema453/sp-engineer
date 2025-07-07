# app/routers/search.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies.subscription_check import check_subscription_usage
from app.models.user import User
from app.db.database import get_db
from app.utils.auth import get_current_user

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("/")
def perform_query(
    query: str,
    user: User = Depends(get_current_user),
    subscription = Depends(check_subscription_usage),
    db: Session = Depends(get_db)
):
    # perform the actual query...
    result = {"result": f"Querying GPT with: {query}"}

    # Increment query usage
    subscription.queries_used += 1
    db.commit()

    return {
        "result": result,
        "queries_used": subscription.queries_used,
        "queries_remaining": subscription.plan.query_limit - subscription.queries_used
    }
