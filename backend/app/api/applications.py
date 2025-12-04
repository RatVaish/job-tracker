from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models import Application as ApplicationModel, Job as JobModel, ApplicationTimeline
from app.schemas import (
    Application,
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationWithDetails,
    MessageResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[Application])
def get_applications(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        status: Optional[str] = Query(None, description="Filter by status"),
        db: Session = Depends(get_db)
):
    """
    Get all applications with optional filters.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **status**: Filter by application status
    """
    query = db.query(ApplicationModel)

    if status:
        query = query.filter(ApplicationModel.status == status)

    # Order by most recent first
    query = query.order_by(ApplicationModel.submitted_at.desc())

    applications = query.offset(skip).limit(limit).all()
    return applications


@router.get("/{application_id}", response_model=ApplicationWithDetails)
def get_application(
        application_id: int,
        db: Session = Depends(get_db)
):
    """
    Get a specific application by ID with all related details.

    Includes: job info, email threads, interviews, timeline events
    """
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found"
        )

    return application


@router.post("/", response_model=Application, status_code=status.HTTP_201_CREATED)
def create_application(
        application: ApplicationCreate,
        db: Session = Depends(get_db)
):
    """
    Create a new application for a job.

    This is typically called when you start working on an application.
    """
    # Verify job exists
    job = db.query(JobModel).filter(JobModel.id == application.job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {application.job_id} not found"
        )

    # Check if application already exists for this job
    existing = db.query(ApplicationModel).filter(
        ApplicationModel.job_id == application.job_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application already exists for this job"
        )

    # Create new application
    db_application = ApplicationModel(**application.model_dump())
    db.add(db_application)
    db.commit()
    db.refresh(db_application)

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=db_application.id,
        event_type="application_started",
        notes="Application draft created"
    )
    db.add(timeline_event)
    db.commit()

    # Update job status
    job.status = "application_started"
    db.commit()

    logger.info(f"Created application {db_application.id} for job {job.job_title}")

    return db_application


@router.patch("/{application_id}", response_model=Application)
def update_application(
        application_id: int,
        application_update: ApplicationUpdate,
        db: Session = Depends(get_db)
):
    """
    Update an application's details.

    Only provided fields will be updated.
    """
    db_application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()

    if not db_application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found"
        )

    # Update only provided fields
    update_data = application_update.model_dump(exclude_unset=True)

    # Track if status changed
    status_changed = "status" in update_data and update_data["status"] != db_application.status
    old_status = db_application.status if status_changed else None

    for field, value in update_data.items():
        setattr(db_application, field, value)

    db.commit()
    db.refresh(db_application)

    # Create timeline event if status changed
    if status_changed:
        timeline_event = ApplicationTimeline(
            application_id=application_id,
            event_type=f"status_changed_to_{update_data['status']}",
            notes=f"Status changed from {old_status} to {update_data['status']}"
        )
        db.add(timeline_event)
        db.commit()

    logger.info(f"Updated application {application_id}")

    return db_application


@router.delete("/{application_id}", response_model=MessageResponse)
def delete_application(
        application_id: int,
        db: Session = Depends(get_db)
):
    """
    Delete an application.

    This will also delete all related data (emails, interviews, timeline).
    """
    db_application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()

    if not db_application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found"
        )

    job_id = db_application.job_id

    db.delete(db_application)
    db.commit()

    # Reset job status if no other applications
    remaining_apps = db.query(ApplicationModel).filter(
        ApplicationModel.job_id == job_id
    ).count()

    if remaining_apps == 0:
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if job:
            job.status = "pending"
            db.commit()

    logger.info(f"Deleted application {application_id}")

    return MessageResponse(
        message="Application deleted successfully",
        detail=f"Deleted application {application_id}"
    )


@router.post("/{application_id}/submit", response_model=Application)
def submit_application(
        application_id: int,
        cover_letter: str,
        db: Session = Depends(get_db)
):
    """
    Submit an application with final cover letter.

    This marks the application as submitted and records the timestamp.
    """
    db_application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()

    if not db_application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found"
        )

    if db_application.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application has already been submitted"
        )

    # Update application
    db_application.cover_letter = cover_letter
    db_application.status = "submitted"
    db_application.submitted_at = datetime.utcnow()

    # Update job status
    job = db.query(JobModel).filter(JobModel.id == db_application.job_id).first()
    if job:
        job.status = "submitted"

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=application_id,
        event_type="submitted",
        notes="Application submitted successfully"
    )
    db.add(timeline_event)

    db.commit()
    db.refresh(db_application)

    logger.info(f"Submitted application {application_id}")

    return db_application


@router.post("/{application_id}/withdraw", response_model=Application)
def withdraw_application(
        application_id: int,
        reason: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Withdraw an application.
    """
    db_application = db.query(ApplicationModel).filter(
        ApplicationModel.id == application_id
    ).first()

    if not db_application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {application_id} not found"
        )

    db_application.status = "withdrawn"

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=application_id,
        event_type="withdrawn",
        notes=reason or "Application withdrawn by user"
    )
    db.add(timeline_event)

    db.commit()
    db.refresh(db_application)

    logger.info(f"Withdrew application {application_id}")

    return db_application


@router.get("/stats/summary")
def get_application_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics about applications.
    """
    from sqlalchemy import func

    total_applications = db.query(func.count(ApplicationModel.id)).scalar()

    # Count by status
    status_counts = db.query(
        ApplicationModel.status,
        func.count(ApplicationModel.id)
    ).group_by(ApplicationModel.status).all()

    # Count submitted applications in last 7 days
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_submissions = db.query(func.count(ApplicationModel.id)).filter(
        ApplicationModel.submitted_at >= week_ago,
        ApplicationModel.status == "submitted"
    ).scalar()

    return {
        "total_applications": total_applications,
        "by_status": {status: count for status, count in status_counts},
        "submitted_last_7_days": recent_submissions
    }
