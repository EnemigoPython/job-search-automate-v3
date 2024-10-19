import json
from collections import defaultdict
from simplegmail import Gmail
from simplegmail.message import Message
from simplegmail.query import construct_query
from websites import AbstractWebsite, LinkedIn, Indeed, \
    IndeedBlock, ExecutiveJobs, CVJobs
from log import Logger
from db import DatabaseConnection
from jobs import JobListing
from driver import Driver

__version__ = 0.21


def load_config() -> dict:
    with open('config.json', 'r') as f:
        config = json.load(f)
        return config


def init_gmail_client():
    logger.log("Initialising Gmail client")
    return Gmail(client_secret_file="credentials.json")


def get_session_websites() -> list[type[AbstractWebsite]]:
    """
    Retrieve the class of websites being used in this session 
    as defined in `config.json`.

    Wrapped in [type] annotation because the objects are not
    initialised.
    """
    session_websites = config['session_websites']
    websites = [LinkedIn, Indeed, IndeedBlock, ExecutiveJobs, CVJobs]
    return [w for w in websites if w.__qualname__ in session_websites]


def init_website_wrappers(
        session_websites: list[type[AbstractWebsite]], 
        sorted_jobs: dict[str, list[JobListing]] | None = None,
        driver: Driver | None = None
    ) -> list[AbstractWebsite]:
    """
    Initialise website wrappers for the current session
    """
    args = (config, logger, db)
    if sorted_jobs is None:
        return [w(*args) for w in session_websites]
    websites = []
    for email, jobs in sorted_jobs.items():
        w = next(w for w in session_websites if w.alert_email() == email)
        websites.append(w(*args, jobs, driver))
    return websites


def get_alert_emails(websites: list[AbstractWebsite]) -> list[str]:
    """
    Retrieve the email string for each website being used in the session
    """
    return [w.alert_email() for w in websites]


def get_job_alert_mail(gmail: Gmail, emails: list[str]):
    """
    Construct a query to retrieve all messages from session email addresses
    """
    query_params = []
    for email in emails:
        query_params.append({
            'sender': email,
            'newer_than': (config['email_check_age'], "day")
        })
    logger.log("Retrieving messages...")
    messages = gmail.get_messages(query=construct_query(*query_params))
    logger.log(f"Found {len(messages)}")
    return messages


def sort_messages(messages: list[Message], websites: list[AbstractWebsite]):
    """
    Sort and filter messages to the correct website wrapper
    """
    for message in messages:
        for website in websites:
            if website.combined_filter(message):
                website.messages.append(message)
                continue


def sort_jobs(jobs: list[JobListing]) -> dict[str, list[JobListing]]:
    """
    Sort retrieved jobs into a dict with email as key
    """
    jobs_dict = defaultdict(list)
    for job in jobs:
        jobs_dict[job.email].append(job)
    return jobs_dict


def find_new_jobs():
    logger.log("Finding new jobs")
    gmail = init_gmail_client()
    session_websites = get_session_websites()
    websites = init_website_wrappers(session_websites)
    emails = get_alert_emails(websites)
    messages = get_job_alert_mail(gmail, emails)
    sort_messages(messages, websites)
    for website in websites:
        website.find_all_jobs()


def apply_for_jobs():
    logger.log("Applying for jobs")
    session_websites = get_session_websites()
    emails = get_alert_emails(session_websites)
    unapplied_jobs = db.retrieve_unapplied_jobs(emails)
    sorted_jobs = sort_jobs(unapplied_jobs)
    with Driver(config, logger) as driver:
        websites = init_website_wrappers(session_websites, sorted_jobs, driver)
        for website in websites:
            website.apply_for_all_jobs()


def main():
    global config
    global logger
    global db
    config = load_config()
    in_production = config['production']
    log_paths = config['log_paths']
    log_file = log_paths['production'] if in_production \
        else log_paths['development']
    with Logger(log_file) as logger:
        mode = "Production" if in_production else "Development"
        logger.log(f'Job-Search-Automate-v3 version {__version__}, "{mode} Mode"')
        with DatabaseConnection(logger, config) as db:
            if config['find_new_jobs']:
                find_new_jobs()
            if config['apply_for_jobs']:
                apply_for_jobs()


if __name__ == '__main__':
    main()
