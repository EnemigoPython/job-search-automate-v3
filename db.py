import os
import sqlite3
from contextlib import closing
from datetime import datetime
from log import Logger
from jobs import JobListing

class DatabaseConnection:
    """
    Sqlite DB connection wrapper
    """
    DB_PATH = os.environ.get('DB_PATH')
    TABLE_NAME = "Job-Search-Automate-v3"
    COLS = [
        "logged_timestamp",
        "title",
        "company",
        "location",
        "salary",
        "email",
        "website",
        "link",
        "description",
        "easy_apply",
        "applied_timestamp",
        "apply_attempts",
        "cover_letter"
    ]  # exclude autoincrement ID
    insert_cols = COLS[:-3]

    def __init__(self, logger: Logger):
        self.logger = logger
        self.conn = sqlite3.connect(self.DB_PATH)
    
    def __enter__(self):
        self.logger.log(f"Connected to {self.DB_PATH}")
        return self

    def __exit__(self, *_exc):
        self.logger.log(f"Connection to {self.DB_PATH} closed")
        self.conn.close()
        return False
    
    @classmethod
    def _format_columns(cls):
        return '(' + ', '.join(cls.insert_cols) + ')'
    
    @classmethod
    def _escaped_values(cls, n: int):
        return '(' + ', '.join('?' * n) + ')'
    
    @staticmethod
    def _get_timestamp():
        now = datetime.now()
        return now.strftime('%Y-%m-%d %H:%M:%S') + f',{now.microsecond // 1000:03d}'
    
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
