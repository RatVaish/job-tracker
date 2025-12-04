from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Interview as InterviewModel, Application as ApplicationModel, ApplicationTimeline
from app.schemas import Interview, InterviewCreate, InterviewUpdate, MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[Interview])
def get_interviews(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        application_id: Optional[int] = Query(None, description="Filter by application ID"),
        status: Optional[str] = Query(None, description="Filter by status"),
        upcoming: Optional[bool] = Query(None, description="Filter upcoming interviews only"),
        db: Session = Depends(get_db)
):
    """
    Get all interviews with optional filters.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **application_id**: Filter by specific application
    - **status**: Filter by interview status
    - **upcoming**: If true, only return interviews scheduled in the future
    """
    query = db.query(InterviewModel)

    if application_id:
        query = query.filter(InterviewModel.application_id == application_id)
    if status:
        query = query.filter(InterviewModel.status == status)
    if upcoming:
        query = query.filter(InterviewModel.scheduled_at > datetime.utcnow())

    # Order by scheduled time (earliest first)
    query = query.order_by(InterviewModel.scheduled_at.asc())

    interviews = query.offset(skip).limit(limit).all()
    return interviews


@router.get("/{interview_id}", response_model=Interview)
def get_interview(
        interview_id: int,
        db: Session = Depends(get_db)
):
    """
    Get a specific interview by ID.
    """
    interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()

    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview with id {interview_id} not found"
        )

    return interview


@router.post("/", response_model=Interview, status_code=status.HTTP_201_CREATED)
def create_interview(
        interview: InterviewCreate,
        db: Session = Depends(get_db)
):
    """
    Create a new interview entry.

    This can be called manually or automatically by email parser.
    """
    # Verify application exists
    application = db.query(ApplicationModel).filter(
        ApplicationModel.id == interview.application_id
    ).first()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id {interview.application_id} not found"
        )

    # Create new interview
    db_interview = InterviewModel(**interview.model_dump())
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)

    # Update application status
    if application.status != "interviewing":
        application.status = "interviewing"

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=interview.application_id,
        event_type="interview_scheduled",
        notes=f"{interview.interview_type} interview scheduled for {interview.scheduled_at}"
    )
    db.add(timeline_event)

    db.commit()

    logger.info(f"Created interview {db_interview.id} for application {interview.application_id}")

    return db_interview


@router.patch("/{interview_id}", response_model=Interview)
def update_interview(
        interview_id: int,
        interview_update: InterviewUpdate,
        db: Session = Depends(get_db)
):
    """
    Update an interview's details.

    Only provided fields will be updated.
    """
    db_interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()

    if not db_interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview with id {interview_id} not found"
        )

    # Update only provided fields
    update_data = interview_update.model_dump(exclude_unset=True)

    # Track if status changed
    status_changed = "status" in update_data and update_data["status"] != db_interview.status

    for field, value in update_data.items():
        setattr(db_interview, field, value)

    db.commit()
    db.refresh(db_interview)

    # Create timeline event if status changed to completed
    if status_changed and update_data["status"] == "completed":
        timeline_event = ApplicationTimeline(
            application_id=db_interview.application_id,
            event_type="interview_completed",
            notes=f"{db_interview.interview_type} interview completed"
        )
        db.add(timeline_event)
        db.commit()

    logger.info(f"Updated interview {interview_id}")

    return db_interview


@router.delete("/{interview_id}", response_model=MessageResponse)
def delete_interview(
        interview_id: int,
        db: Session = Depends(get_db)
):
    """
    Delete an interview.
    """
    db_interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()

    if not db_interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview with id {interview_id} not found"
        )

    db.delete(db_interview)
    db.commit()

    logger.info(f"Deleted interview {interview_id}")

    return MessageResponse(
        message="Interview deleted successfully",
        detail=f"Deleted interview {interview_id}"
    )


@router.post("/{interview_id}/complete", response_model=Interview)
def mark_interview_complete(
        interview_id: int,
        notes: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Mark an interview as completed.

    Optionally add notes about how it went.
    """
    db_interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()

    if not db_interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview with id {interview_id} not found"
        )

    db_interview.status = "completed"
    if notes:
        db_interview.notes = notes

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=db_interview.application_id,
        event_type="interview_completed",
        notes=notes or f"{db_interview.interview_type} interview completed"
    )
    db.add(timeline_event)

    db.commit()
    db.refresh(db_interview)

    logger.info(f"Marked interview {interview_id} as completed")

    return db_interview


@router.post("/{interview_id}/cancel", response_model=Interview)
def cancel_interview(
        interview_id: int,
        reason: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    Cancel an interview.
    """
    db_interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()

    if not db_interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview with id {interview_id} not found"
        )

    db_interview.status = "cancelled"

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=db_interview.application_id,
        event_type="interview_cancelled",
        notes=reason or "Interview cancelled"
    )
    db.add(timeline_event)

    db.commit()
    db.refresh(db_interview)

    logger.info(f"Cancelled interview {interview_id}")

    return db_interview


@router.post("/{interview_id}/reschedule", response_model=Interview)
def reschedule_interview(
        interview_id: int,
        new_scheduled_at: datetime,
        db: Session = Depends(get_db)
):
    """
    Reschedule an interview to a new time.
    """
    db_interview = db.query(InterviewModel).filter(InterviewModel.id == interview_id).first()

    if not db_interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview with id {interview_id} not found"
        )

    old_time = db_interview.scheduled_at
    db_interview.scheduled_at = new_scheduled_at
    db_interview.status = "rescheduled"

    # Create timeline event
    timeline_event = ApplicationTimeline(
        application_id=db_interview.application_id,
        event_type="interview_rescheduled",
        notes=f"Interview rescheduled from {old_time} to {new_scheduled_at}"
    )
    db.add(timeline_event)

    db.commit()
    db.refresh(db_interview)

    logger.info(f"Rescheduled interview {interview_id}")

    return db_interview


@router.get("/upcoming/next-7-days", response_model=List[Interview])
def get_upcoming_interviews(
        db: Session = Depends(get_db)
):
    """
    Get all interviews scheduled in the next 7 days.

    Useful for dashboard/notification features.
    """
    now = datetime.utcnow()
    week_from_now = now + timedelta(days=7)

    interviews = db.query(InterviewModel).filter(
        InterviewModel.scheduled_at >= now,
        InterviewModel.scheduled_at <= week_from_now,
        InterviewModel.status.in_(["scheduled", "needs_response", "rescheduled"])
    ).order_by(InterviewModel.scheduled_at.asc()).all()

    return interviews


@router.get("/application/{application_id}", response_model=List[Interview])
def get_interviews_by_application(
        application_id: int,
        db: Session = Depends(get_db)
):
    """
    Get all interviews for a specific application.

    Ordered by scheduled time (earliest first).
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

    interviews = db.query(InterviewModel).filter(
        InterviewModel.application_id == application_id
    ).order_by(InterviewModel.scheduled_at.asc()).all()

    return interviews


@router.get("/needs-response/urgent")
def get_urgent_interviews(
        db: Session = Depends(get_db)
):
    """
    Get interviews that need response urgently (deadline within 24 hours).
    """
    now = datetime.utcnow()
    tomorrow = now + timedelta(hours=24)

    urgent_interviews = db.query(InterviewModel).filter(
        InterviewModel.deadline_at.isnot(None),
        InterviewModel.deadline_at <= tomorrow,
        InterviewModel.deadline_at > now,
        InterviewModel.status == "needs_response"
    ).order_by(InterviewModel.deadline_at.asc()).all()

    return {
        "count": len(urgent_interviews),
        "interviews": [
            {
                "id": interview.id,
                "application_id": interview.application_id,
                "interview_type": interview.interview_type,
                "scheduled_at": interview.scheduled_at,
                "deadline_at": interview.deadline_at,
                "hours_remaining": (interview.deadline_at - now).total_seconds() / 3600
            }
            for interview in urgent_interviews
        ]
    }


@router.get("/stats/summary")
def get_interview_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics about interviews.
    """
    from sqlalchemy import func

    total_interviews = db.query(func.count(InterviewModel.id)).scalar()

    # Count by status
    status_counts = db.query(
        InterviewModel.status,
        func.count(InterviewModel.id)
    ).group_by(InterviewModel.status).all()

    # Count by type
    type_counts = db.query(
        InterviewModel.interview_type,
        func.count(InterviewModel.id)
    ).group_by(InterviewModel.interview_type).all()

    # Upcoming interviews
    now = datetime.utcnow()
    upcoming_count = db.query(func.count(InterviewModel.id)).filter(
        InterviewModel.scheduled_at > now,
        InterviewModel.status.in_(["scheduled", "needs_response"])
    ).scalar()

    return {
        "total_interviews": total_interviews,
        "upcoming_interviews": upcoming_count,
        "by_status": {status: count for status, count in status_counts},
        "by_type": {interview_type: count for interview_type, count in type_counts}
    }
