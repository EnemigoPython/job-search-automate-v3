import re
import traceback
from abc import ABC, abstractmethod
from simplegmail.message import Message
from bs4 import BeautifulSoup, Tag, NavigableString
from jobs import JobListing
from log import Logger, LogLevel
from db import DatabaseConnection
from driver import Driver, By

class AbstractWebsite(ABC):
    """
    ABC to be inherited by all websites sending job alerts
    """
    def __init__(
            self, 
            config: dict,
            logger: Logger,
            db: DatabaseConnection,
            jobs: list[JobListing] | None = None,
            driver: Driver | None = None
    ):
        self.config = config
        self.logger = logger
        self.db = db
        self.jobs = jobs or []
        self.driver = driver
        self.messages = []
        num_jobs = len(self.jobs)
        self.logger.log(f'Initialised website wrapper: {self} with {num_jobs} jobs.')
        super().__init__()
    
    def __str__(self):
        return f"{self.name()} ({self.alert_email()})"

    @staticmethod
    @abstractmethod
    def alert_email() -> str:
        """
        The email address the alert comes from.
        """
    
    @staticmethod
    @abstractmethod
    def name() -> str:
        """
        The plaintext name of the website.
        """

    @staticmethod
    @abstractmethod
    def multiple_listings() -> bool:
        """
        Do messages contain a single listing or multiple.
        """

    @staticmethod
    def automatable() -> bool:
        """
        Are the website links automatable - we assume yes unless overriden.
        """
        return True
    
    @staticmethod
    def support_all_applications() -> bool:
        """
        If `True` can apply to jobs even if `easy_apply` is `False`
        """
        return False
    
    def generic_filter(self, message: Message) -> bool:
        """
        Used to check if a message came from this website.
        """
        email = message.sender.split("<")[1].split(">")[0]
        return email == self.alert_email()
    
    def quality_filter(self, message: Message) -> bool:
        """
        Used to filter messages by keywords that indicate a good job match.

        By default: `True` accepts all messages.
        """
        return True
    
    def combined_filter(self, message: Message) -> bool:
        """
        Combines both filters as criteria for storing a message
        """
        return self.generic_filter(message) and self.quality_filter(message)
    
    def parse_message_html(self, message: Message):
        return BeautifulSoup(message.html, 'html.parser')
    
    def extract_salary(self, text: str) -> str | None:
        """
        Extract a salary substring from a given string
        """
        # We use `.find` to not exclude a range of salary e.g. "£60K-70K"
        if (substr := text.find('£')) != -1:
            salary = re.split(r'\s{2,}', text[substr:])[0].replace(')', '').replace('(', '')
        else:
            salary = None
        # truncate salary to 'X a year'
        if salary:
            salary = re.split(r'([A-Z])', salary)[0]
        return salary
    
    def job_title_filter(self, job_title: str):
        """
        Filter applied after job collation to check the job title matches
        likely prospects.
        """
        return any(i in job_title for i in self.config['title_checks']) and \
            not any(i in job_title for i in self.config['negative_title_checks'])
    
    def find_all_jobs(self):
        """
        Loop through all messages and get job listing info
        """
        self.logger.log(f'Finding jobs for {self}...')
        for message in self.messages:
            self.find_jobs(message)
        all_jobs = len(self.jobs)
        self.logger.log(f'{all_jobs} found')
        self.jobs = [j for j in self.jobs if self.job_title_filter(j.title)]
        discarded_jobs = all_jobs - len(self.jobs)
        self.logger.log(f'{discarded_jobs} discarded')
        self.db.save_job_listings(self.jobs)
    
    @abstractmethod
    def find_jobs(self, message: Message):
        """
        Retrieve job listings from the email
        """
    
    def apply_for_all_jobs(self):
        """
        Loop through and apply to all jobs
        """
        if self.driver is None:
            raise AttributeError(f"No driver was passed to {self}")
        if not self.automatable():
            self.logger.log(f"Skipping {self} - marked as not automatable")
            return
        self.logger.log(f'Applying for jobs with {self}...')
        for e, job in enumerate(self.jobs, 1):
            # if not self.support_all_applications() and not job.easy_apply:
            #     self.logger.log(
            #         f"Skipping job {e}: row ID {job.row_id} (application type not supported by {self})"
            #     )
            #     continue
            try:
                self.logger.log(
                    f"Applying for job {e} of {len(self.jobs)}: row ID {job.row_id} in database"
                )
                self.apply_for_job(job)
            except Exception as e:
                trace_stack = f"""\n {''.join(traceback.format_exception(
                    type(e), e, e.__traceback__
                ))}"""
                self.logger.log(
                    f"Error applying for job; dumping trace stack: {trace_stack}", 
                    LogLevel.ERROR
                )
                # self.db.increment_apply_attempts(job.row_id)
            return
    
    @abstractmethod
    def apply_for_job(self, job: JobListing):
        """
        Apply for a job using link
        """

class LinkedIn(AbstractWebsite):
    @staticmethod
    def alert_email():
        return "jobs-listings@linkedin.com"
    
    @staticmethod
    def name():
        return "LinkedIn"
    
    @staticmethod
    def multiple_listings():
        return True
    
    def extract_job_listing(self, text: str, link: str):
        listing_elements = re.split(r'\s{2,}', text.lstrip())
        title = listing_elements[0].split("-")[0].strip()
        company = listing_elements[1].split(" · ")[0]
        location = listing_elements[1].split(" · ")[1]
        easy_apply = 'Easy Apply' in text
        salary = self.extract_salary(text)
        return JobListing(
            None,
            title, 
            company, 
            location, 
            salary,
            self.alert_email(),
            self.name(),
            link,
            None,
            easy_apply
        )
    
    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        jobs_table = html.find('table').find_all('table')[2]
        raw_job_listings = jobs_table.find_all('table')
        for job_outer in raw_job_listings:
            try:
                job_inner = job_outer.find("table").find("table").find("table")
                job_link = job_inner.find('a')
                if job_link:
                    self.jobs.append(
                        self.extract_job_listing(job_inner.get_text(), job_link['href'])
                    )
            except AttributeError:
                continue
    
    def next_button_found(self):
        self.driver.sleep(3)  # allow page to update
        return self.driver.wait_until(
            self.driver.Condition.ELEMENT_FOUND,
            (By.CSS_SELECTOR, "button[data-easy-apply-next-button=''"),
            2
        )

    def apply_for_job(self, job: JobListing):
        """
        Apply for a job using link
        """
        self.driver.get(job.link)
        application_card = self.driver.find_element(By.CSS_SELECTOR, "div.t-14.artdeco-card")
        try:
            easy_apply_btn = application_card.find_element(
                By.CSS_SELECTOR, "button.jobs-apply-button"
            )
            self.logger.log("Clicking 'Easy Apply'...")
            easy_apply_btn.click()
            while self.next_button_found():
                self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "button[aria-label='Continue to next step']"
                ).click()
            self.driver.find_element(
                By.CSS_SELECTOR, 
                "button[aria-label='Review your application']"
            ).click()
            self.driver.execute_script("document.querySelector('.jobs-easy-apply-modal__content').scroll(0, 1000)")
            self.driver.find_element(
                By.CSS_SELECTOR,
                "label[for='follow-company-checkbox']"
            ).click()
            self.driver.find_element(
                By.CSS_SELECTOR, 
                "button[aria-label='Submit application']"
            ).click()
            self.logger.log("Application complete")
            self.driver.sleep(10)
            self.db.mark_job_listing_as_applied(job.row_id)

        except self.driver.Exceptions.NOT_FOUND:
            self.driver.find_element(By.XPATH, "//span[contains(., 'No longer accepting')]")
            self.logger.log("Applications for this job have closed.", LogLevel.WARNING)
            self.db.mark_job_listing_as_closed(job.row_id)
        self.driver.sleep(20)

class Indeed(AbstractWebsite):
    @staticmethod
    def alert_email():
        return "invitetoapply@indeed.com"
    
    @staticmethod
    def name():
        return "Indeed"
    
    @staticmethod
    def multiple_listings():
        return False
    
    def quality_filter(self, message: Message) -> bool:
        return any(i in message.subject for i in self.config['title_checks']) \
        and not any(i in message.subject for i in self.config['negative_title_checks'])
    
    def find_jobs(self, message: Message):
        job_title, company = message.subject.strip().split(' @ ')
        html = self.parse_message_html(message)
        job_table = html.find_all('table')[5]
        link = job_table.find('a')['href']
        location = job_table.find_all('p')[1].get_text().strip()
        salary = self.extract_salary(job_table.get_text())
        job_listing = JobListing(
            None,
            job_title,
            company,
            location,
            salary,
            self.alert_email(),
            self.name(),
            link,
            None,
            False
        )
        self.jobs.append(job_listing)
    
    def apply_for_job(self, job: JobListing):
        """
        Apply for a job using link
        """
    
class IndeedBlock(AbstractWebsite):
    @staticmethod
    def alert_email():
        return "alert@indeed.com"
    
    @staticmethod
    def name():
        return "Indeed"
    
    @staticmethod
    def multiple_listings():
        return False
    
    def is_valid_float(self, s: str):
        """
        Companies with ratings have orphaned td with a float e.g. '3.9'
        """
        try:
            float(s)
            return True
        except ValueError:
            return False
    
    def adjust_for_company_rating(self, sections: list[str]):
        """
        We are scraping by text index, but some variation throws this off.
        Jobs with a rating have extra content, so we account for this while indexing.
        """
        return 2 if any(self.is_valid_float(s) for s in sections) else 0
    
    def get_location(self, sections: list[str]):
        """
        In an effort to scrape location properly we have to wrangle the data
        """
        location = sections[3 + self.adjust_for_company_rating(sections)]
        return location.replace('\xa0', ' ')

    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        job_table = html.find_all('table')[7]
        job_sections = job_table.find_all('table')
        for job_section in job_sections:
            a_tag = job_section.find('a')
            if a_tag:
                job_section_text = [j.get_text() for j in job_section.find_all('td')]
                job_title = job_section_text[0]
                company = job_section_text[2]
                location = self.get_location(job_section_text)
                description = job_section_text[-2]
                easy_apply = 'Easily apply' in job_section.get_text()
                salary = self.extract_salary(job_section.get_text())
                link = a_tag['href']
                job_listing = JobListing(
                    None,
                    job_title,
                    company,
                    location,
                    salary,
                    self.alert_email(),
                    self.name(),
                    link,
                    description,
                    easy_apply
                )
                self.jobs.append(job_listing)
    
    def apply_for_job(self, job: JobListing):
        """
        Apply for a job using link
        """

class ExecutiveJobs(AbstractWebsite):
    @staticmethod
    def alert_email():
        return "info@executiveplacements.com"
    
    @staticmethod
    def name():
        return "Executive Placement Jobs"
    
    @staticmethod
    def multiple_listings():
        return True
    
    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        job_table = html.find('table').find('table').find_all('tr')[1].find('td')
        sections: list[NavigableString|Tag] = job_table.children
        new_listing = True
        job_title = ""
        location = ""
        link = ""
        description = ""
        for section in sections:
            try:
                if isinstance(section, Tag) and 'href' in section.attrs.keys():
                    new_listing = True
                    if job_title and link and location and description:
                        job_listing = JobListing(
                            None,
                            job_title,
                            None,
                            location,
                            None,
                            self.alert_email(),
                            self.name(),
                            link,
                            description,
                            False
                        )
                        self.jobs.append(job_listing)
                    job_title = section.get_text()
                    link = section['href']
                    description = ""
                elif new_listing and section.get_text():
                    location = section.get_text().split("Location: ")[1]
                    new_listing = False
                else:
                    description += section.get_text()
            except IndexError:
                continue
    
    def apply_for_job(self, job: JobListing):
        """
        Apply for a job using link
        """

class CVJobs(AbstractWebsite):
    @staticmethod
    def alert_email():
        return "admin@jobs.cv-library.co.uk"
    
    @staticmethod
    def name():
        return "CV-Library"
    
    @staticmethod
    def multiple_listings():
        return True
    
    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        job_sections: list[NavigableString|Tag] = html.find('table').find_all('article')
        for job_section in job_sections:
            a_tag = job_section.find('a')
            job_title = a_tag.get_text().strip().replace('\ufeff', '')
            link = a_tag['href']
            p_tags = job_section.find_all('p')
            if len(p_tags) < 2:
                continue
            p_text = [p.get_text() for p in p_tags]
            if len(p_tags) == 3:
                salary = p_text[0]
                location = p_text[1]
                description = p_text[2]
            else:
                salary = None
                location = p_text[0]
                description = p_text[1]
            job_listing = JobListing(
                None,
                job_title,
                None,
                location,
                salary,
                self.alert_email(),
                self.name(),
                link,
                description,
                False
            )
            self.jobs.append(job_listing)
    
    def apply_for_job(self, job: JobListing):
        """
        Apply for a job using link
        """
        # print(0 / 0)
