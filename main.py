import json
from simplegmail import Gmail
from simplegmail.message import Message
from simplegmail.query import construct_query
from websites import AbstractWebsite, LinkedIn, Indeed, \
    IndeedBlock, ExecutiveJobs, CVJobs
from log import Logger
from db import DatabaseConnection

__version__ = 0.19


def load_config() -> dict:
    with open('config.json', 'r') as f:
        config = json.load(f)
        return config


def init_gmail_client():
    logger.log("Initialising Gmail client")
    return Gmail(client_secret_file="credentials.json")


def get_alert_emails(websites: list[AbstractWebsite]) -> list[str]:
    """
    Retrieve the email string for each website being used in the session
    """
    return [w.alert_email for w in websites]


def get_job_alert_mail(gmail: Gmail, emails: list[str]):
    """
    Construct a query to retrieve all messages from session email addresses
    """
    query_params = []
    for email in emails:
        query_params.append({
            'sender': email,
            'newer_than': (5, "day")
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


def main():
    # easier than passing them around
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
        with DatabaseConnection(logger) as db:
            gmail = init_gmail_client()
            # initialise website class wrappers
            args = (config, logger, db)
            websites: list[AbstractWebsite] = [
                LinkedIn(*args),
                Indeed(*args),
                IndeedBlock(*args),
                ExecutiveJobs(*args),
                CVJobs(*args)
            ]
            emails = get_alert_emails(websites)
            messages = get_job_alert_mail(gmail, emails)
            sort_messages(messages, websites)
            for website in websites:
                website.find_all_jobs()


if __name__ == '__main__':
    main()
