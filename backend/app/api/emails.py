from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import EmailThread as EmailThreadModel, Application as ApplicationModel
from app.schemas import EmailThread, EmailThreadCreate, EmailThreadUpdate, MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[EmailThread])
def get_emails(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        application_id: Optional[int] = Query(None, description="Filter by application ID"),
        email_type: Optional[str] = Query(None, description="Filter by email type"),
        is_read: Optional[bool] = Query(None, description="Filter by read status"),
        db: Session = Depends(get_db)
):
    """
    Get all email threads with optional filters.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **application_id**: Filter by specific application
    - **email_type**: Filter by type (interview_invite, rejection, etc.)
    - **is_read**: Filter by read/unread status
    """
    query = db.query(EmailThreadModel)

    if application_id:
        query = query.filter(EmailThreadModel.application_id == application_id)
    if email_type:
        query = query.filter(EmailThreadModel.email_type == email_type)
    if is_read is not None:
        query = query.filter(EmailThreadModel.is_read == is_read)

    # Order by most recent first
    query = query.order_by(EmailThreadModel.received_at.desc())

    emails = query.offset(skip).limit(limit).all()
    return emails


@router.get("/{email_id}", response_model=EmailThread)
def get_email(
        email_id: int,
        db: Session = Depends(get_db)
):
    """
    Get a specific email thread by ID.
    """
    email = db.query(EmailThreadModel).filter(EmailThreadModel.id == email_id).first()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )

    return email


@router.post("/", response_model=EmailThread, status_code=status.HTTP_201_CREATED)
def create_email(
        email: EmailThreadCreate,
        db: Session = Depends(get_db)
):
    """
    Create a new email thread entry.

    This is typically called automatically by the email monitoring service.
    """
    # Verify application exists
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == email.application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {email.application_id} not found"
        )

    # Create new email thread
    db_email = EmailThreadModel(**email.model_dump())
    db.add(db_email)
    db.commit()
    db.refresh(db_email)

    logger.info(f"Created email thread {db_email.id} for application {email.application_id}")

    return db_email


@router.patch("/{email_id}", response_model=EmailThread)
def update_email(
        email_id: int,
        email_update: EmailThreadUpdate,
        db: Session = Depends(get_db)
):
    """
    Update an email thread.

    Typically used to mark as read or reclassify email type.
    """
    db_email = db.query(EmailThreadModel).filter(EmailThreadModel.id == email_id).first()

    if not db_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )

    # Update only provided fields
    update_data = email_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_email, field, value)

    db.commit()
    db.refresh(db_email)

    logger.info(f"Updated email {email_id}")

    return db_email


@router.delete("/{email_id}", response_model=MessageResponse)
def delete_email(
        email_id: int,
        db: Session = Depends(get_db)
):
    """
    Delete an email thread.
    """
    db_email = db.query(EmailThreadModel).filter(EmailThreadModel.id == email_id).first()

    if not db_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )

    db.delete(db_email)
    db.commit()

    logger.info(f"Deleted email {email_id}")

    return MessageResponse(
        message="Email deleted successfully",
        detail=f"Deleted email thread {email_id}"
    )


@router.post("/{email_id}/mark-read", response_model=EmailThread)
def mark_email_read(
        email_id: int,
        db: Session = Depends(get_db)
):
    """
    Mark an email as read.
    """
    db_email = db.query(EmailThreadModel).filter(EmailThreadModel.id == email_id).first()

    if not db_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )

    db_email.is_read = True
    db.commit()
    db.refresh(db_email)

    logger.info(f"Marked email {email_id} as read")

    return db_email


@router.post("/{email_id}/mark-unread", response_model=EmailThread)
def mark_email_unread(
        email_id: int,
        db: Session = Depends(get_db)
):
    """
    Mark an email as unread.
    """
    db_email = db.query(EmailThreadModel).filter(EmailThreadModel.id == email_id).first()

    if not db_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )

    db_email.is_read = False
    db.commit()
    db.refresh(db_email)

    logger.info(f"Marked email {email_id} as unread")

    return db_email


@router.get("/unread/count")
def get_unread_count(
        application_id: Optional[int] = Query(None),
        db: Session = Depends(get_db)
):
    """
    Get count of unread emails.

    Optionally filter by application_id.
    """
    from sqlalchemy import func

    query = db.query(func.count(EmailThreadModel.id)).filter(
        EmailThreadModel.is_read == False
    )

    if application_id:
        query = query.filter(EmailThreadModel.application_id == application_id)

    unread_count = query.scalar()

    return {
        "unread_count": unread_count,
        "application_id": application_id
    }


@router.get("/application/{application_id}", response_model=List[EmailThread])
def get_emails_by_application(
        application_id: int,
        db: Session = Depends(get_db)
):
    """
    Get all emails for a specific application.

    Ordered by most recent first.
    """
    # Verify application exists
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found"
        )

    emails = db.query(EmailThreadModel).filter(
        EmailThreadModel.application_id == application_id
    ).order_by(EmailThreadModel.received_at.desc()).all()

    return emails


@router.get("/stats/summary")
def get_email_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics about emails.
    """
    from sqlalchemy import func

    total_emails = db.query(func.count(EmailThreadModel.id)).scalar()
    unread_emails = db.query(func.count(EmailThreadModel.id)).filter(
        EmailThreadModel.is_read == False
    ).scalar()

    # Count by type
    type_counts = db.query(
        EmailThreadModel.email_type,
        func.count(EmailThreadModel.id)
    ).group_by(EmailThreadModel.email_type).all()

    # Count emails with attachments
    with_attachments = db.query(func.count(EmailThreadModel.id)).filter(
        EmailThreadModel.has_attachment == True
    ).scalar()

    return {
        "total_emails": total_emails,
        "unread_emails": unread_emails,
        "with_attachments": with_attachments,
        "by_type": {email_type: count for email_type, count in type_counts}
    }
