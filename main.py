from simplegmail import Gmail
from simplegmail.message import Message
from simplegmail.query import construct_query
from websites import AbstractWebsite, LinkedIn, Indeed, \
    IndeedBlock, ExecutiveJobs, CVJobs


def init_gmail_client():
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
    messages = gmail.get_messages(query=construct_query(*query_params))
    print(messages)
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
    gmail = init_gmail_client()
    # initialise website class wrappers
    websites: list[AbstractWebsite] = [
        LinkedIn(),
        Indeed(),
        IndeedBlock(),
        ExecutiveJobs(),
        CVJobs()
    ]
    emails = get_alert_emails(websites)
    messages = get_job_alert_mail(gmail, emails)
    # TODO: filter seen before messages
    sort_messages(messages, websites)
    for website in websites:
        print(f'\n\n{website} {len(website.messages)}: \n{website.messages}')
        website.find_all_jobs()
        for job in website.jobs:
            print(f'{job.company=}, {job.title=}, {job.location=}, {job.salary=}')


if __name__ == '__main__':
    main()
