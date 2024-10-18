from dataclasses import dataclass

@dataclass
class JobListing:
    title: str
    company: str
    location: str | None
    salary: str | None
    website: str
    link: str
    description: str | None
    linkedin_easy_apply: bool
