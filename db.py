import os
import sqlite3
from dataclasses import dataclass, fields
from contextlib import closing
from datetime import datetime
from log import Logger
from jobs import JobListing

@dataclass
class DatabaseRow:
    ID: int
    logged_timestamp: str
    title: str
    company: str | None
    location: str | None
    salary: str | None
    email: str
    website: str
    link: str
    description: str
    easy_apply: bool
    applied_timestamp: str | None
    apply_attempts: int
    cover_letter: str | None

class DatabaseConnection:
    """
    Sqlite DB connection wrapper
    """
    DB_PATH = os.environ.get('DB_PATH')
    TABLE_NAME = "Job-Search-Automate-v3"
    find_insert_cols = [f.name for f in fields(DatabaseRow)[1:-3]]

    def __init__(self, logger: Logger, config: dict):
        self.logger = logger
        self.config = config
        self.conn = sqlite3.connect(self.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        # we will save rows when we load data from the DB for internal lookup
        self._rows: list[DatabaseRow]
    
    def __enter__(self):
        self.logger.log(f"Connected to {self.DB_PATH}")
        return self

    def __exit__(self, *_exc):
        self.logger.log(f"Connection to {self.DB_PATH} closed")
        self.conn.close()
        return False
    
    @classmethod
    def _format_columns(cls):
        return '(' + ', '.join(cls.find_insert_cols) + ')'
    
    @classmethod
    def _escaped_values(cls, n: int):
        return '(' + ', '.join('?' * n) + ')'
    
    @staticmethod
    def _get_timestamp():
        now = datetime.now()
        return now.strftime('%Y-%m-%d %H:%M:%S') + f',{now.microsecond // 1000:03d}'
    
    @staticmethod
    def _format_emails(emails: list[str]):
        quoted_emails = [f"'{e}'" for e in emails]
        return '(' + ', '.join(quoted_emails) + ')'
    
    @staticmethod
    def _format_job_listing(job_listing: JobListing):
        return (
            DatabaseConnection._get_timestamp(),
            job_listing.title,
            job_listing.company,
            job_listing.location,
            job_listing.salary,
            job_listing.email,
            job_listing.website,
            job_listing.link,
            job_listing.description,
            job_listing.easy_apply
        )
    
    @staticmethod
    def row_to_job_listing(row: DatabaseRow):
        return JobListing(
            row.ID,
            row.title,
            row.company,
            row.location,
            row.salary,
            row.email,
            row.website,
            row.link,
            row.description,
            bool(row.easy_apply)
        )

    def save_job_listings(self, job_listings: list[JobListing]):
        new_entries = 0
        with closing(self.conn.cursor()) as cursor:
            for job_listing in job_listings:
                try:
                    cursor.execute(f"""
                        INSERT INTO '{self.TABLE_NAME}'
                        {DatabaseConnection._format_columns()}
                        VALUES
                        {DatabaseConnection._escaped_values(10)}
                    """, DatabaseConnection._format_job_listing(job_listing))
                    new_entries += 1
                except sqlite3.IntegrityError:
                    continue
            self.conn.commit()
        self.logger.log(f"{new_entries} rows added")
    
    def retrieve_unapplied_jobs(self, emails: list[str]) -> list[JobListing]:
        max_retries = self.config['max_apply_retries']
        with closing(self.conn.cursor()) as cursor:
            query = list(cursor.execute(f"""
                SELECT * FROM '{self.TABLE_NAME}' 
                WHERE applied_timestamp IS NULL
                AND apply_attempts < {max_retries}
                AND email in {self._format_emails(emails)}
            """))
            self._rows = [DatabaseRow(*i) for i in query]
            unapplied_jobs = [self.row_to_job_listing(i) for i in self._rows]
            self.logger.log(f"{len(unapplied_jobs)} jobs to apply for")
            return unapplied_jobs
    
    def mark_job_listing_as_closed(self, row_id: int):
        """
        If a listing is no longer available, set retries to 99 in the database.

        This will be shorthand for "don't try to apply for this one again".
        """
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(f"""
                UPDATE '{self.TABLE_NAME}' 
                SET apply_attempts = 99
                WHERE ID = {row_id}
            """)
            self.logger.log(f"Marked row ID {row_id} as closed.")
            self.conn.commit()

    def increment_apply_attempts(self, row_id: int):
        db_row = next(i for i in self._rows if i.ID == row_id)
        incremented_attempts = db_row.apply_attempts + 1
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(f"""
                UPDATE '{self.TABLE_NAME}' 
                SET apply_attempts = {incremented_attempts}
                WHERE ID = {row_id}
            """)
            self.logger.log(
                f"Incremented row ID {row_id} attempts to {incremented_attempts}."
            )
            self.conn.commit()
    
    def mark_job_listing_as_applied(self, row_id: int):
        """
        Insert a timestamp in `applied_timestamp` to mark as applied.
        """
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(f"""
                UPDATE '{self.TABLE_NAME}' 
                SET applied_timestamp = '{self._get_timestamp()}'
                WHERE ID = {row_id}
            """)
            self.logger.log(f"Marked row ID {row_id} as applied.")
            self.conn.commit()
