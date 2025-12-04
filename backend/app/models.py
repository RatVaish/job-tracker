from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Job(Base):
    """
    Represents a job posting discovered from job boards.
    """
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    job_board_url = Column(Text, nullable=False, unique=True)  # Prevent duplicate scraping
    job_board_source = Column(String(50), nullable=False)  # 'linkedin', 'indeed', etc.
    location = Column(String(255))
    salary_range = Column(String(100))
    description = Column(Text)
    requirements = Column(Text)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    match_score = Column(Float)  # Optional: AI-calculated match score (0-100)
    status = Column(
        String(50),
        default='pending',
        index=True
    )  # 'pending', 'application_started', 'ready_for_review', 'submitted', 'closed'

    # Relationships
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.job_title}', company='{self.company}')>"


class Application(Base):
    """
    Represents a job application you've submitted or are preparing.
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    application_url = Column(Text)  # URL where you applied
    submitted_at = Column(DateTime(timezone=True))
    cover_letter = Column(Text)  # Your final cover letter
    resume_version = Column(String(100))  # Which resume version you used
    status = Column(
        String(50),
        default='draft',
        index=True
    )  # 'draft', 'submitted', 'interviewing', 'rejected', 'accepted', 'withdrawn'

    # Relationships
    job = relationship("Job", back_populates="applications")
    email_threads = relationship("EmailThread", back_populates="application", cascade="all, delete-orphan")
    interviews = relationship("Interview", back_populates="application", cascade="all, delete-orphan")
    timeline_events = relationship("ApplicationTimeline", back_populates="application", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Application(id={self.id}, job_id={self.job_id}, status='{self.status}')>"


class EmailThread(Base):
    """
    Tracks email communications related to an application.
    """
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    email_subject = Column(String(500))
    from_email = Column(String(255), index=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    email_body = Column(Text)
    email_type = Column(
        String(50),
        index=True
    )  # 'interview_invite', 'rejection', 'follow_up', 'acknowledgment', 'other'
    has_attachment = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)

    # Relationships
    application = relationship("Application", back_populates="email_threads")

    def __repr__(self):
        return f"<EmailThread(id={self.id}, type='{self.email_type}', from='{self.from_email}')>"


class Interview(Base):
    """
    Tracks scheduled interviews for applications.
    """
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    interview_type = Column(String(50))  # 'phone', 'video', 'technical', 'onsite', 'assessment'
    scheduled_at = Column(DateTime(timezone=True), index=True)
    deadline_at = Column(DateTime(timezone=True))  # When you need to respond by
    duration_minutes = Column(Integer)
    location = Column(String(255))  # Physical location or video call link
    interviewer_name = Column(String(255))
    interviewer_email = Column(String(255))
    notes = Column(Text)  # Your prep notes
    status = Column(
        String(50),
        default='scheduled',
        index=True
    )  # 'scheduled', 'completed', 'cancelled', 'needs_response', 'rescheduled'

    # Relationships
    application = relationship("Application", back_populates="interviews")

    def __repr__(self):
        return f"<Interview(id={self.id}, type='{self.interview_type}', status='{self.status}')>"


class ApplicationTimeline(Base):
    """
    Tracks all events in the application lifecycle.
    Creates an audit trail of what happened when.
    """
    __tablename__ = "application_timeline"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(
        String(50),
        nullable=False,
        index=True
    )  # 'discovered', 'application_started', 'submitted', 'viewed', 'interview_scheduled', 'rejected', 'accepted'
    event_date = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    notes = Column(Text)
    extra_data = Column(Text)  # Changed from 'metadata' to 'extra_data' - JSON string for additional data

    # Relationships
    application = relationship("Application", back_populates="timeline_events")

    def __repr__(self):
        return f"<ApplicationTimeline(id={self.id}, type='{self.event_type}', date={self.event_date})>"


class ScraperLog(Base):
    """
    Logs scraping activity to track what was scraped and when.
    Helps with debugging and rate limiting.
    """
    __tablename__ = "scraper_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_board = Column(String(50), nullable=False, index=True)  # 'linkedin', 'indeed'
    scrape_started_at = Column(DateTime(timezone=True), server_default=func.now())
    scrape_ended_at = Column(DateTime(timezone=True))
    jobs_found = Column(Integer, default=0)
    jobs_added = Column(Integer, default=0)  # New jobs (not duplicates)
    status = Column(String(50), default='running')  # 'running', 'completed', 'failed'
    error_message = Column(Text)
    search_keywords = Column(String(500))
    search_location = Column(String(255))

    def __repr__(self):
        return f"<ScraperLog(id={self.id}, board='{self.job_board}', found={self.jobs_found})>"
