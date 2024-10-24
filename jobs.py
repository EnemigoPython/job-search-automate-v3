from dataclasses import dataclass

@dataclass
class JobListing:
    row_id: int | None  # primary key for DB lookup
    title: str
    company: str | None  # not all job boards visibly post the company
    location: str | None
    salary: str | None
    email: str
    website: str
    link: str
    description: str | None
    easy_apply: bool
