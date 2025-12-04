from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import time
import random
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Base class for all job board scrapers.
    Provides common functionality and enforces interface.
    """

    def __init__(self, delay_min: int = 2, delay_max: int = 5):
        """
        Initialize scraper with rate limiting.

        Args:
            delay_min: Minimum seconds between requests
            delay_max: Maximum seconds between requests
        """
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.jobs_scraped = []
        self.scrape_start_time = None
        self.scrape_end_time = None

    def random_delay(self):
        """
        Sleep for a random amount of time to avoid bot detection.
        """
        delay = random.uniform(self.delay_min, self.delay_max)
        logger.debug(f"Sleeping for {delay:.2f} seconds")
        time.sleep(delay)

    @abstractmethod
    def build_search_url(self, keywords: str, location: str) -> str:
        """
        Build the search URL for the job board.

        Args:
            keywords: Search keywords (e.g., "graduate electrical engineer")
            location: Location to search (e.g., "London")

        Returns:
            Complete search URL
        """
        pass

    @abstractmethod
    def parse_job_listing(self, job_element) -> Optional[Dict]:
        """
        Parse a single job listing element and extract job details.

        Args:
            job_element: HTML element containing job info

        Returns:
            Dictionary with job details or None if parsing fails
        """
        pass

    @abstractmethod
    def scrape_search_page(self, url: str) -> List[Dict]:
        """
        Scrape a single search results page.

        Args:
            url: URL of the search results page

        Returns:
            List of job dictionaries
        """
        pass

    def scrape(
            self,
            keywords: List[str],
            locations: List[str],
            max_jobs: int = 50
    ) -> List[Dict]:
        """
        Main scraping method. Scrapes multiple keyword/location combinations.

        Args:
            keywords: List of search keywords
            locations: List of locations to search
            max_jobs: Maximum number of jobs to scrape

        Returns:
            List of job dictionaries
        """
        self.scrape_start_time = datetime.utcnow()
        self.jobs_scraped = []

        logger.info(f"Starting scrape for {self.__class__.__name__}")
        logger.info(f"Keywords: {keywords}")
        logger.info(f"Locations: {locations}")

        try:
            for keyword in keywords:
                for location in locations:
                    if len(self.jobs_scraped) >= max_jobs:
                        logger.info(f"Reached max jobs limit ({max_jobs})")
                        break

                    logger.info(f"Scraping: {keyword} in {location}")

                    # Build search URL
                    url = self.build_search_url(keyword, location)
                    logger.debug(f"Search URL: {url}")

                    # Scrape the page
                    jobs = self.scrape_search_page(url)

                    # Add to results
                    self.jobs_scraped.extend(jobs)
                    logger.info(f"Found {len(jobs)} jobs for '{keyword}' in '{location}'")

                    # Rate limiting
                    if keyword != keywords[-1] or location != locations[-1]:
                        self.random_delay()

                if len(self.jobs_scraped) >= max_jobs:
                    break

        except Exception as e:
            logger.error(f"Error during scraping: {e}", exc_info=True)

        finally:
            self.scrape_end_time = datetime.utcnow()
            duration = (self.scrape_end_time - self.scrape_start_time).total_seconds()
            logger.info(f"Scraping completed. Found {len(self.jobs_scraped)} jobs in {duration:.2f}s")

        return self.jobs_scraped[:max_jobs]

    def get_user_agent(self) -> str:
        """
        Get a realistic user agent string to avoid bot detection.
        """
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return random.choice(user_agents)
