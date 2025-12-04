from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.deps import validate_pagination
from app.database import get_db
from app.models import Job as JobModel
from app.schemas import Job, JobCreate, JobUpdate, JobWithApplications, MessageResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[Job])
def get_jobs(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        status: Optional[str] = Query(None, description="Filter by status"),
        company: Optional[str] = Query(None, description="Filter by company name"),
        job_board: Optional[str] = Query(None, description="Filter by job board source"),
        db: Session = Depends(get_db)
):
    """
    Get all jobs with optional filters.

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **status**: Filter by job status (e.g., 'pending', 'submitted')
    - **company**: Filter by company name (partial match)
    - **job_board**: Filter by job board source (e.g., 'linkedin', 'indeed')
    """
    query = db.query(JobModel)

    # Apply filters
    if status:
        query = query.filter(JobModel.status == status)
    if company:
        query = query.filter(JobModel.company.ilike(f"%{company}%"))
    if job_board:
        query = query.filter(JobModel.job_board_source == job_board)

    # Order by most recent first
    query = query.order_by(JobModel.discovered_at.desc())

    jobs = query.offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=JobWithApplications)
def get_job(
        job_id: int,
        db: Session = Depends(get_db)
):
    """
    Get a specific job by ID, including all related applications.
    """
    job = db.query(JobModel).filter(JobModel.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    return job


@router.post("/", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(
        job: JobCreate,
        db: Session = Depends(get_db)
):
    """
    Create a new job posting.

    This is typically called by the scraper, but can also be used manually.
    """
    # Check if job already exists (by URL to avoid duplicates)
    existing_job = db.query(JobModel).filter(
        JobModel.job_board_url == job.job_board_url
    ).first()

    if existing_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job with this URL already exists"
        )

    # Create new job
    db_job = JobModel(**job.model_dump())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    logger.info(f"Created new job: {db_job.job_title} at {db_job.company}")

    return db_job


@router.patch("/{job_id}", response_model=Job)
def update_job(
        job_id: int,
        job_update: JobUpdate,
        db: Session = Depends(get_db)
):
    """
    Update a job's details.

    Only provided fields will be updated.
    """
    db_job = db.query(JobModel).filter(JobModel.id == job_id).first()

    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    # Update only provided fields
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_job, field, value)

    db.commit()
    db.refresh(db_job)

    logger.info(f"Updated job {job_id}: {db_job.job_title}")

    return db_job


@router.delete("/{job_id}", response_model=MessageResponse)
def delete_job(
        job_id: int,
        db: Session = Depends(get_db)
):
    """
    Delete a job posting.

    This will also delete all related applications (cascade delete).
    """
    db_job = db.query(JobModel).filter(JobModel.id == job_id).first()

    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    job_title = db_job.job_title
    company = db_job.company

    db.delete(db_job)
    db.commit()

    logger.info(f"Deleted job: {job_title} at {company}")

    return MessageResponse(
        message="Job deleted successfully",
        detail=f"Deleted: {job_title} at {company}"
    )


@router.get("/stats/summary")
def get_job_stats(db: Session = Depends(get_db)):
    """
    Get summary statistics about jobs.

    Returns counts by status, job board, etc.
    """
    from sqlalchemy import func

    total_jobs = db.query(func.count(JobModel.id)).scalar()

    # Count by status
    status_counts = db.query(
        JobModel.status,
        func.count(JobModel.id)
    ).group_by(JobModel.status).all()

    # Count by job board
    board_counts = db.query(
        JobModel.job_board_source,
        func.count(JobModel.id)
    ).group_by(JobModel.job_board_source).all()

    return {
        "total_jobs": total_jobs,
        "by_status": {status: count for status, count in status_counts},
        "by_job_board": {board: count for board, count in board_counts}
    }


@router.post("/{job_id}/mark-closed", response_model=Job)
def mark_job_closed(
        job_id: int,
        db: Session = Depends(get_db)
):
    """
    Mark a job as closed (no longer accepting applications).
    """
    db_job = db.query(JobModel).filter(JobModel.id == job_id).first()

    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    db_job.status = "closed"
    db.commit()
    db.refresh(db_job)

    logger.info(f"Marked job {job_id} as closed")

    return db_job


@router.post("/scrape/indeed")
def trigger_indeed_scrape(
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        max_jobs: Optional[int] = None,
        db: Session = Depends(get_db)
):
    """
    Manually trigger Indeed scraping.

    If keywords/locations not provided, uses values from .env config.
    """
    from app.services.job_service import JobScraperService

    scraper_service = JobScraperService(db)
    result = scraper_service.scrape_and_save_indeed(
        keywords=keywords,
        locations=locations,
        max_jobs=max_jobs
    )

    return result
