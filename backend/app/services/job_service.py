from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Dict
import logging

from app.models import Job, ScraperLog
from app.scrapers.indeed import IndeedScraper
from app.config import settings

logger = logging.getLogger(__name__)


class JobScraperService:
    """
    Service to handle job scraping and database insertion.
    """

    def __init__(self, db: Session):
        self.db = db
        self.indeed_scraper = IndeedScraper()

    def scrape_and_save_indeed(
            self,
            keywords: List[str] = None,
            locations: List[str] = None,
            max_jobs: int = None
    ) -> Dict:
        """
        Scrape Indeed and save jobs to database.

        Returns dict with statistics.
        """
        # Use config defaults if not provided
        if keywords is None:
            keywords = settings.scraping_keywords_list
        if locations is None:
            locations = settings.scraping_locations_list
        if max_jobs is None:
            max_jobs = settings.MAX_JOBS_PER_SCRAPE

        # Create scraper log
        scraper_log = ScraperLog(
            job_board="indeed",
            status="running",
            search_keywords=", ".join(keywords),
            search_location=", ".join(locations)
        )
        self.db.add(scraper_log)
        self.db.commit()

        try:
            logger.info(f"Starting Indeed scrape: {keywords} in {locations}")

            # Scrape jobs
            jobs_scraped = self.indeed_scraper.scrape(
                keywords=keywords,
                locations=locations,
                max_jobs=max_jobs
            )

            logger.info(f"Scraped {len(jobs_scraped)} jobs from Indeed")

            # Save to database
            jobs_added = 0
            jobs_duplicate = 0

            for job_data in jobs_scraped:
                try:
                    # Check if job already exists by URL
                    existing_job = self.db.query(Job).filter(
                        Job.job_board_url == job_data['job_board_url']
                    ).first()

                    if existing_job:
                        logger.debug(f"Job already exists: {job_data['job_title']}")
                        jobs_duplicate += 1
                        continue

                    # Create new job
                    job = Job(**job_data)
                    self.db.add(job)
                    self.db.commit()

                    jobs_added += 1
                    logger.info(f"Added job: {job.job_title} at {job.company}")

                except IntegrityError as e:
                    self.db.rollback()
                    logger.warning(f"Duplicate job (integrity error): {job_data.get('job_title')}")
                    jobs_duplicate += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Error saving job: {e}", exc_info=True)

            # Update scraper log
            scraper_log.jobs_found = len(jobs_scraped)
            scraper_log.jobs_added = jobs_added
            scraper_log.status = "completed"
            self.db.commit()

            result = {
                "jobs_found": len(jobs_scraped),
                "jobs_added": jobs_added,
                "jobs_duplicate": jobs_duplicate,
                "status": "success"
            }

            logger.info(f"Scraping completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error during scraping: {e}", exc_info=True)

            # Update scraper log with error
            scraper_log.status = "failed"
            scraper_log.error_message = str(e)
            self.db.commit()

            return {
                "jobs_found": 0,
                "jobs_added": 0,
                "jobs_duplicate": 0,
                "status": "error",
                "error": str(e)
            }

    def scrape_and_save_gradcracker(
            self,
            keywords: List[str] = None,
            locations: List[str] = None,
            max_jobs: int = None
    ) -> Dict:
        """
        Scrape Gradcracker and save jobs to database.

        Returns dict with statistics.
        """
        from app.scrapers.gradcracker import GradcrackerScraper

        # Use config defaults if not provided
        if keywords is None:
            keywords = settings.scraping_keywords_list
        if locations is None:
            locations = settings.scraping_locations_list
        if max_jobs is None:
            max_jobs = settings.MAX_JOBS_PER_SCRAPE

        # Create scraper log
        scraper_log = ScraperLog(
            job_board="gradcracker",
            status="running",
            search_keywords=", ".join(keywords),
            search_location=", ".join(locations)
        )
        self.db.add(scraper_log)
        self.db.commit()

        try:
            logger.info(f"Starting Gradcracker scrape: {keywords} in {locations}")

            # Create scraper
            gradcracker_scraper = GradcrackerScraper()

            # Scrape jobs
            jobs_scraped = gradcracker_scraper.scrape(
                keywords=keywords,
                locations=locations,
                max_jobs=max_jobs
            )

            logger.info(f"Scraped {len(jobs_scraped)} jobs from Gradcracker")

            # Save to database (same logic as Indeed)
            jobs_added = 0
            jobs_duplicate = 0

            for job_data in jobs_scraped:
                try:
                    existing_job = self.db.query(Job).filter(
                        Job.job_board_url == job_data['job_board_url']
                    ).first()

                    if existing_job:
                        logger.debug(f"Job already exists: {job_data['job_title']}")
                        jobs_duplicate += 1
                        continue

                    job = Job(**job_data)
                    self.db.add(job)
                    self.db.commit()

                    jobs_added += 1
                    logger.info(f"Added job: {job.job_title} at {job.company}")

                except IntegrityError as e:
                    self.db.rollback()
                    logger.warning(f"Duplicate job: {job_data.get('job_title')}")
                    jobs_duplicate += 1
                except Exception as e:
                    self.db.rollback()
                    logger.error(f"Error saving job: {e}", exc_info=True)

            # Update scraper log
            scraper_log.jobs_found = len(jobs_scraped)
            scraper_log.jobs_added = jobs_added
            scraper_log.status = "completed"
            self.db.commit()

            result = {
                "jobs_found": len(jobs_scraped),
                "jobs_added": jobs_added,
                "jobs_duplicate": jobs_duplicate,
                "status": "success"
            }

            logger.info(f"Scraping completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error during scraping: {e}", exc_info=True)

            scraper_log.status = "failed"
            scraper_log.error_message = str(e)
            self.db.commit()

            return {
                "jobs_found": 0,
                "jobs_added": 0,
                "jobs_duplicate": 0,
                "status": "error",
                "error": str(e)
            }
