from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()


def start_scheduler():
    """
    Start the background scheduler for automated tasks.
    """
    if not settings.SCRAPING_ENABLED:
        logger.info("Scraping is disabled in config, scheduler not started")
        return

    from app.tasks.background_jobs import scrape_indeed_job

    # Schedule Indeed scraping
    scheduler.add_job(
        func=scrape_indeed_job,
        trigger=IntervalTrigger(seconds=settings.SCRAPING_INTERVAL),
        id='scrape_indeed',
        name='Scrape Indeed for jobs',
        replace_existing=True,
        next_run_time=datetime.now()  # Run immediately on startup
    )

    scheduler.start()
    logger.info(f"Scheduler started. Indeed scraping every {settings.SCRAPING_INTERVAL} seconds")


def stop_scheduler():
    """
    Stop the background scheduler.
    """
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
