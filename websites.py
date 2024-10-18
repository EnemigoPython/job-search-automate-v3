import re
from abc import ABC, abstractmethod
from simplegmail.message import Message
from bs4 import BeautifulSoup, Tag, NavigableString
from jobs import JobListing
from log import Logger, LogLevel
from db import DatabaseConnection

class AbstractWebsite(ABC):
    """
    ABC to be inherited by all websites sending job alerts
    """
    def __init__(
            self, 
            config: dict,
            logger: Logger,
            db: DatabaseConnection,
            messages: list[Message] | None = None, 
            jobs: list[JobListing] | None = None
        ):
        self.config = config
        self.logger = logger
        self.db = db
        if messages is None:
            self.messages = []
        else:
            self.messages = messages
        if jobs is None:
            self.jobs = []
        else:
            self.jobs = jobs
        num_messages = len(self.messages)
        num_jobs = len(self.jobs)
        self.logger.log(f'Initialised website wrapper: {self}. {num_messages} messages & {num_jobs} jobs.')
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
            self.alert_email,
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
        return "Indeed"
    
    @property
    def multiple_listings(self):
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
            job_title,
            company,
            location,
            salary,
            self.alert_email,
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
        return "Indeed"
    
    @property
    def multiple_listings(self):
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
                    job_title,
                    company,
                    location,
                    salary,
                    self.alert_email,
                    self.name,
                    link,
                    description,
                    easy_apply
                )
                self.jobs.append(job_listing)

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
                            job_title,
                            None,
                            location,
                            None,
                            self.alert_email,
                            self.name,
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
                job_title,
                None,
                location,
                salary,
                self.alert_email,
                self.name,
                link,
                description,
                False
            )
            self.jobs.append(job_listing)
