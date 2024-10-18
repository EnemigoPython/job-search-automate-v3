from abc import ABC, abstractmethod
from simplegmail.message import Message
from bs4 import BeautifulSoup
from jobs import JobListing
import re

class AbstractWebsite(ABC):
    """
    ABC to be inherited by all websites sending job alerts
    """

    # generic checks to apply when scraping job listings
    title_checks = ('Python', 'C#', 'Javascript', 'Backend', 'Junior', 'Graduate', 'DevOps', 'Software')
    negative_title_checks = ('C++', 'Go', 'Golang', 'Rust', 'Chinese', 'Turkish')
    location_checks = ('London', 'Oxford', 'Cambridge')

    def __init__(
            self, 
            messages: list[Message] | None = None, 
            jobs: list[JobListing] | None = None
        ):
        if messages is None:
            self.messages = []
        else:
            self.messages = messages
        if jobs is None:
            self.jobs = []
        else:
            self.jobs = jobs
        super().__init__()
    
    def __str__(self):
        return f"{self.name} ({self.alert_email})"

    @property
    @abstractmethod
    def alert_email(self) -> str:
        """
        The email address the alert comes from.
        """
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        The plaintext name of the website.
        """

    @property
    @abstractmethod
    def multiple_listings(self) -> bool:
        """
        Do messages contain a single listing or multiple.
        """

    @property
    def automatable(self) -> bool:
        """
        Are the website links automatable - we assume yes unless overriden.
        """
        return True
    
    def generic_filter(self, message: Message) -> bool:
        """
        Used to check if a message came from this website.
        """
        email = message.sender.split("<")[1].split(">")[0]
        return email == self.alert_email
    
    def quality_filter(self, message: Message) -> bool:
        """
        Used to filter each message by keywords that indicate a good job match.

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

        Note: we use `.find` to not exclude a range of salary e.g. "£60K-70K"
        """
        if (substr := text.find('£')) != -1:
            return re.split(r'\s{2,}', text[substr:])[0].replace(')', '').replace('(', '')
        else:
            return None
    
    def find_all_jobs(self):
        """
        Loop through all messages and get job listing info
        """
        for message in self.messages:
            self.find_jobs(message)
    
    @abstractmethod
    def find_jobs(self, message: Message):
        """
        Retrieve job listings from the email
        """
        ...

class LinkedIn(AbstractWebsite):
    @property
    def alert_email(self):
        return "jobs-listings@linkedin.com"
    
    @property
    def name(self):
        return "LinkedIn"
    
    @property
    def multiple_listings(self):
        return True
    
    def extract_job_listing(self, text: str, link: str):
        listing_elements = re.split(r'\s{2,}', text.lstrip())
        title = listing_elements[0].split("-")[0].strip()
        company = listing_elements[1].split(" · ")[0]
        location = listing_elements[1].split(" · ")[1]
        easy_apply = 'Easy Apply' in text
        salary = self.extract_salary(text)
        return JobListing(
            title, 
            company, 
            location, 
            salary,
            self.name,
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

class Indeed(AbstractWebsite):
    @property
    def alert_email(self):
        return "invitetoapply@indeed.com"
    
    @property
    def name(self):
        return "Indeed Individual Listings"
    
    @property
    def multiple_listings(self):
        return False
    
    def quality_filter(self, message: Message) -> bool:
        return any(i in message.subject for i in self.title_checks) \
        and not any(i in message.subject for i in self.negative_title_checks)
    
    def find_jobs(self, message: Message):
        job_title, company = message.subject.strip().split(' @ ')
        html = self.parse_message_html(message)
        job_table = html.find_all('table')[5]
        link = job_table.find('a')['href']
        location = job_table.find_all('p')[1].get_text().strip()
        salary = self.extract_salary(job_table.get_text())
        # truncate salary to 'X a year'
        if salary:
            salary = re.split(r'([A-Z])', salary)[0]
        job_listing = JobListing(
            job_title,
            company,
            location,
            salary,
            self.name,
            link,
            None,
            False
        )
        self.jobs.append(job_listing)
    
class IndeedBlock(AbstractWebsite):
    @property
    def alert_email(self):
        return "alert@indeed.com"
    
    @property
    def name(self):
        return "Indeed Block Listings"
    
    @property
    def multiple_listings(self):
        return False
    
    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        print(self.name)

class ExecutiveJobs(AbstractWebsite):
    @property
    def alert_email(self):
        return "info@executiveplacements.com"
    
    @property
    def name(self):
        return "Executive Placement Jobs"
    
    @property
    def multiple_listings(self):
        return True
    
    @property
    def automatable(self):
        return False
    
    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        print(self.name)

class CVJobs(AbstractWebsite):
    @property
    def alert_email(self):
        return "admin@jobs.cv-library.co.uk"
    
    @property
    def name(self):
        return "CV-Library"
    
    @property
    def multiple_listings(self):
        return True
    
    def find_jobs(self, message: Message):
        html = self.parse_message_html(message)
        print(self.name)
