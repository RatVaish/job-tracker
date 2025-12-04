from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses pydantic-settings for validation and type safety.
    """

    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    DEBUG: bool = True
    SECRET_KEY: str
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Job Tracker API"

    # Database Configuration
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # OpenAI Configuration
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 1000
    OPENAI_TEMPERATURE: float = 0.3

    # Email Configuration
    EMAIL_HOST: str
    EMAIL_PORT: int = 993
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str
    EMAIL_USE_TLS: bool = True
    EMAIL_CHECK_INTERVAL: int = 3600  # seconds

    # SMTP Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_USE_TLS: bool = True

    # Job Scraping Configuration
    SCRAPING_ENABLED: bool = True
    SCRAPING_INTERVAL: int = 7200  # seconds
    SCRAPING_KEYWORDS: str = "software engineer,backend developer,python developer"
    SCRAPING_LOCATIONS: str = "United Kingdom,London,Remote"
    SCRAPING_JOB_BOARDS: str = "linkedin,indeed"

    # LinkedIn Configuration
    LINKEDIN_EMAIL: Optional[str] = None
    LINKEDIN_PASSWORD: Optional[str] = None

    # Indeed Configuration
    INDEED_API_KEY: Optional[str] = None

    # Notification Configuration
    PUSH_NOTIFICATIONS_ENABLED: bool = True
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security & CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    CORS_ALLOW_CREDENTIALS: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/job_tracker.log"

    # Application Settings
    MAX_APPLICATIONS_PER_DAY: int = 10
    AUTO_APPLY_ENABLED: bool = False
    TIMEZONE: str = "Europe/London"

    # Rate Limiting
    SCRAPER_DELAY_MIN: int = 2
    SCRAPER_DELAY_MAX: int = 5
    MAX_JOBS_PER_SCRAPE: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields in .env
    )

    # Helper properties to parse comma-separated values
    @property
    def scraping_keywords_list(self) -> List[str]:
        """Convert comma-separated keywords to list"""
        return [k.strip() for k in self.SCRAPING_KEYWORDS.split(",")]

    @property
    def scraping_locations_list(self) -> List[str]:
        """Convert comma-separated locations to list"""
        return [l.strip() for l in self.SCRAPING_LOCATIONS.split(",")]

    @property
    def scraping_job_boards_list(self) -> List[str]:
        """Convert comma-separated job boards to list"""
        return [b.strip() for b in self.SCRAPING_JOB_BOARDS.split(",")]

    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert comma-separated origins to list"""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache settings instance.
    Using lru_cache ensures we only load .env once.
    """
    return Settings()


# Convenience instance for importing
settings = get_settings()