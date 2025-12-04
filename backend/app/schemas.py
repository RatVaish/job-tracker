from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ============================================================================
# Job Schemas
# ============================================================================

class JobBase(BaseModel):
    """Base schema for Job with common fields"""
    job_title: str = Field(..., max_length=255)
    company: str = Field(..., max_length=255)
    job_board_url: str
    job_board_source: str = Field(..., max_length=50)
    location: Optional[str] = Field(None, max_length=255)
    salary_range: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    requirements: Optional[str] = None
    match_score: Optional[float] = Field(None, ge=0, le=100)


class JobCreate(JobBase):
    """Schema for creating a new job"""
    pass


class JobUpdate(BaseModel):
    """Schema for updating a job (all fields optional)"""
    job_title: Optional[str] = Field(None, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    salary_range: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    requirements: Optional[str] = None
    match_score: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[str] = Field(None, max_length=50)


class Job(JobBase):
    """Schema for returning job data"""
    id: int
    discovered_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class JobWithApplications(Job):
    """Schema for job with related applications"""
    applications: List["Application"] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Application Schemas
# ============================================================================

class ApplicationBase(BaseModel):
    """Base schema for Application"""
    job_id: int
    application_url: Optional[str] = None
    cover_letter: Optional[str] = None
    resume_version: Optional[str] = Field(None, max_length=100)


class ApplicationCreate(ApplicationBase):
    """Schema for creating a new application"""
    pass


class ApplicationUpdate(BaseModel):
    """Schema for updating an application (all fields optional)"""
    application_url: Optional[str] = None
    cover_letter: Optional[str] = None
    resume_version: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=50)


class Application(ApplicationBase):
    """Schema for returning application data"""
    id: int
    submitted_at: Optional[datetime] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class ApplicationWithDetails(Application):
    """Schema for application with related data"""
    job: Job
    email_threads: List["EmailThread"] = []
    interviews: List["Interview"] = []
    timeline_events: List["ApplicationTimeline"] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# EmailThread Schemas
# ============================================================================

class EmailThreadBase(BaseModel):
    """Base schema for EmailThread"""
    application_id: int
    email_subject: Optional[str] = Field(None, max_length=500)
    from_email: str = Field(..., max_length=255)
    email_body: Optional[str] = None
    email_type: str = Field(..., max_length=50)
    has_attachment: bool = False


class EmailThreadCreate(EmailThreadBase):
    """Schema for creating a new email thread"""
    pass


class EmailThreadUpdate(BaseModel):
    """Schema for updating an email thread"""
    email_type: Optional[str] = Field(None, max_length=50)
    is_read: Optional[bool] = None


class EmailThread(EmailThreadBase):
    """Schema for returning email thread data"""
    id: int
    received_at: datetime
    is_read: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Interview Schemas
# ============================================================================

class InterviewBase(BaseModel):
    """Base schema for Interview"""
    application_id: int
    interview_type: str = Field(..., max_length=50)
    scheduled_at: datetime
    deadline_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=255)
    interviewer_name: Optional[str] = Field(None, max_length=255)
    interviewer_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class InterviewCreate(InterviewBase):
    """Schema for creating a new interview"""
    pass


class InterviewUpdate(BaseModel):
    """Schema for updating an interview"""
    interview_type: Optional[str] = Field(None, max_length=50)
    scheduled_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=255)
    interviewer_name: Optional[str] = Field(None, max_length=255)
    interviewer_email: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)


class Interview(InterviewBase):
    """Schema for returning interview data"""
    id: int
    status: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ApplicationTimeline Schemas
# ============================================================================

class ApplicationTimelineBase(BaseModel):
    """Base schema for ApplicationTimeline"""
    application_id: int
    event_type: str = Field(..., max_length=50)
    notes: Optional[str] = None
    extra_data: Optional[str] = None

class ApplicationTimelineCreate(ApplicationTimelineBase):
    """Schema for creating a timeline event"""
    pass


class ApplicationTimeline(ApplicationTimelineBase):
    """Schema for returning timeline event data"""
    id: int
    event_date: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# ScraperLog Schemas
# ============================================================================

class ScraperLogBase(BaseModel):
    """Base schema for ScraperLog"""
    job_board: str = Field(..., max_length=50)
    search_keywords: Optional[str] = Field(None, max_length=500)
    search_location: Optional[str] = Field(None, max_length=255)


class ScraperLogCreate(ScraperLogBase):
    """Schema for creating a scraper log"""
    pass


class ScraperLogUpdate(BaseModel):
    """Schema for updating a scraper log"""
    scrape_ended_at: Optional[datetime] = None
    jobs_found: Optional[int] = Field(None, ge=0)
    jobs_added: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(None, max_length=50)
    error_message: Optional[str] = None


class ScraperLog(ScraperLogBase):
    """Schema for returning scraper log data"""
    id: int
    scrape_started_at: datetime
    scrape_ended_at: Optional[datetime] = None
    jobs_found: int
    jobs_added: int
    status: str
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Response Schemas (for common API responses)
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Generic paginated response"""
    total: int
    page: int
    page_size: int
    items: List[BaseModel]


# Update forward references for nested models
JobWithApplications.model_rebuild()
ApplicationWithDetails.model_rebuild()
