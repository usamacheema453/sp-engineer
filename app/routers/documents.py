# app/routers/documents.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.dependencies.subscription_check import check_subscription_usage

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload")
def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    subscription = Depends(lambda: check_subscription_usage(
        user=user,
        db=get_db(),
        check_document=True
    ))
):
    # You can save file to disk, S3, etc. Placeholder logic:
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb+") as f:
        f.write(file.file.read())

    # Increment document count
    subscription.documents_uploaded += 1
    db.commit()

    return {
        "message": f"File '{file.filename}' uploaded successfully.",
        "documents_uploaded": subscription.documents_uploaded,
        "documents_remaining": subscription.plan.document_upload_limit - subscription.documents_uploaded
    }
