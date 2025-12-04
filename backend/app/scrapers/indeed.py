from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service  # ADD THIS
from webdriver_manager.chrome import ChromeDriverManager  # ADD THIS
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import logging
from urllib.parse import quote_plus
import time

from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    """
    Scraper for Indeed UK job board using Selenium.
    """

    def __init__(self, delay_min: int = 2, delay_max: int = 5, headless: bool = True):
        super().__init__(delay_min, delay_max)
        self.base_url = "https://uk.indeed.com"
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """Initialize Selenium WebDriver"""
        if self.driver is None:
            options = Options()

            if self.headless:
                options.add_argument('--headless')

            # Anti-detection options
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            # Set user agent
            options.add_argument(f'user-agent={self.get_user_agent()}')

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)

            # Remove webdriver flag
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def _close_driver(self):
        """Close Selenium WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def build_search_url(self, keywords: str, location: str) -> str:
        """
        Build Indeed search URL.
        """
        encoded_keywords = quote_plus(keywords)
        encoded_location = quote_plus(location)

        url = f"{self.base_url}/jobs?q={encoded_keywords}&l={encoded_location}"
        return url

    def scrape_search_page(self, url: str) -> List[Dict]:
        """
        Scrape a single Indeed search results page using Selenium.
        """
        jobs = []

        try:
            self._init_driver()

            logger.info(f"Loading page: {url}")
            self.driver.get(url)

            # Wait for job cards to load
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "job_seen_beacon")))

            # Small random delay to appear more human
            time.sleep(self.delay_min)

            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Find job cards
            job_cards = soup.find_all('div', class_='job_seen_beacon')

            if not job_cards:
                job_cards = soup.find_all('div', class_='cardOutline')

            if not job_cards:
                job_cards = soup.find_all('td', class_='resultContent')

            logger.info(f"Found {len(job_cards)} job cards on page")

            for card in job_cards:
                job = self.parse_job_listing(card)
                if job:
                    jobs.append(job)

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}", exc_info=True)

        return jobs

    def parse_job_listing(self, job_element) -> Optional[Dict]:
        """
        Parse a single Indeed job card and extract details.
        """
        try:
            job_data = {}

            # Job title and link
            title_elem = job_element.find('h2', class_='jobTitle')
            if not title_elem:
                title_elem = job_element.find('a', class_='jcs-JobTitle')

            if title_elem:
                title_link = title_elem.find('a') or title_elem
                job_data['job_title'] = title_link.get_text(strip=True)

                # Build full URL
                job_link = title_link.get('href', '')
                if job_link.startswith('/'):
                    job_data['job_board_url'] = f"{self.base_url}{job_link}"
                else:
                    job_data['job_board_url'] = job_link
            else:
                logger.warning("Could not find job title, skipping")
                return None

            # Company name
            company_elem = job_element.find('span', class_='companyName')
            if not company_elem:
                company_elem = job_element.find('span', {'data-testid': 'company-name'})

            if company_elem:
                job_data['company'] = company_elem.get_text(strip=True)
            else:
                job_data['company'] = "Unknown Company"

            # Location
            location_elem = job_element.find('div', class_='companyLocation')
            if not location_elem:
                location_elem = job_element.find('div', {'data-testid': 'text-location'})

            if location_elem:
                job_data['location'] = location_elem.get_text(strip=True)
            else:
                job_data['location'] = "Location not specified"

            # Salary
            salary_elem = job_element.find('div', class_='salary-snippet')
            if not salary_elem:
                salary_elem = job_element.find('div', {'data-testid': 'attribute_snippet_testid'})

            if salary_elem:
                job_data['salary_range'] = salary_elem.get_text(strip=True)
            else:
                job_data['salary_range'] = None

            # Job description snippet
            description_elem = job_element.find('div', class_='job-snippet')
            if not description_elem:
                description_elem = job_element.find('div', {'class': 'underShelfFooter'})

            if description_elem:
                job_data['description'] = description_elem.get_text(strip=True)
            else:
                job_data['description'] = ""

            job_data['job_board_source'] = 'indeed'
            job_data['requirements'] = None

            logger.debug(f"Parsed job: {job_data['job_title']} at {job_data['company']}")

            return job_data

        except Exception as e:
            logger.error(f"Error parsing job listing: {e}", exc_info=True)
            return None

    def scrape(
            self,
            keywords: List[str],
            locations: List[str],
            max_jobs: int = 50
    ) -> List[Dict]:
        """
        Scrape Indeed for jobs matching keywords and locations.
        """
        try:
            # Initialize driver once for all searches
            self._init_driver()

            self.jobs_scraped = []

            for keyword in keywords:
                for location in locations:
                    if len(self.jobs_scraped) >= max_jobs:
                        break

                    logger.info(f"Scraping: {keyword} in {location}")
                    url = self.build_search_url(keyword, location)

                    jobs = self.scrape_search_page(url)
                    self.jobs_scraped.extend(jobs)

                    logger.info(f"Found {len(jobs)} jobs for '{keyword}' in '{location}'")

                    # Random delay between searches
                    self.random_delay()

                if len(self.jobs_scraped) >= max_jobs:
                    break

            return self.jobs_scraped[:max_jobs]

        finally:
            # Always close driver when done
            self._close_driver()

    def scrape_with_pagination(
            self,
            keywords: List[str],
            locations: List[str],
            max_pages: int = 3,
            max_jobs: int = 50
    ) -> List[Dict]:
        """
        Scrape multiple pages of Indeed results.
        """
        try:
            self.jobs_scraped = []

            for keyword in keywords:
                for location in locations:
                    if len(self.jobs_scraped) >= max_jobs:
                        break

                    for page in range(max_pages):
                        if len(self.jobs_scraped) >= max_jobs:
                            break

                        start = page * 10
                        base_url = self.build_search_url(keyword, location)
                        url = f"{base_url}&start={start}"

                        logger.info(f"Scraping page {page + 1}: {keyword} in {location}")

                        jobs = self.scrape_search_page(url)

                        if not jobs:
                            logger.info(f"No jobs found on page {page + 1}, stopping pagination")
                            break

                        self.jobs_scraped.extend(jobs)

                        if page < max_pages - 1:
                            self.random_delay()

                if len(self.jobs_scraped) >= max_jobs:
                    break

            return self.jobs_scraped[:max_jobs]

        finally:
            self._close_driver()
