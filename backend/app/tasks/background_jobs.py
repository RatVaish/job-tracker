import logging
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.job_service import JobScraperService
from app.config import settings

logger = logging.getLogger(__name__)


def scrape_indeed_job():
    """
    Background job to scrape Indeed.
    This runs on a schedule.
    """
    logger.info("=== Starting scheduled Indeed scrape ===")

    db = SessionLocal()
    try:
        scraper_service = JobScraperService(db)

        result = scraper_service.scrape_and_save_indeed(
            keywords=settings.scraping_keywords_list,
            locations=settings.scraping_locations_list,
            max_jobs=settings.MAX_JOBS_PER_SCRAPE
        )

        logger.info(f"=== Scheduled scrape completed: {result} ===")

    except Exception as e:
        logger.error(f"Error in scheduled scrape: {e}", exc_info=True)
    finally:
        db.close()


# You can add more background jobs here
def scrape_all_job_boards():
    """
    Scrape all enabled job boards.
    """
    logger.info("=== Starting scrape for all job boards ===")

    db = SessionLocal()
    try:
        scraper_service = JobScraperService(db)

        # Scrape Indeed
        if 'indeed' in settings.scraping_job_boards_list:
            logger.info("Scraping Indeed...")
            indeed_result = scraper_service.scrape_and_save_indeed()
            logger.info(f"Indeed result: {indeed_result}")

        # Add more job boards here as we build them
        # if 'reed' in settings.scraping_job_boards_list:
        #     logger.info("Scraping Reed...")
        #     reed_result = scraper_service.scrape_and_save_reed()

        logger.info("=== All job boards scraped ===")

    except Exception as e:
        logger.error(f"Error scraping job boards: {e}", exc_info=True)
    finally:
        db.close()
