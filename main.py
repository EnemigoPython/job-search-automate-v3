import re
from simplegmail import Gmail
from simplegmail.message import Message
from simplegmail.query import construct_query
from websites import AbstractWebsite, LinkedIn, Indeed, \
    IndeedBlock, ExecutiveJobs, CVJobs

# HREF_PATTERN = r'href\s*=\s*["\']?([^"\'\s>]+)'
# HREF_PATTERN = r'href\s*=\s*["\']?([^"\'\s>]+)["\']?\s*>(?:\s*)I\'m interested'
HREF_PATTERN = r'<a\s+href=["\']([^"\']+)["\'].*?>\s*I\'m interested\s*</a>'


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

def filter_indeed_message(message: Message):
    '''
    Attempt to filter for only jobs that we should bother applying for
    '''
    title_checks = ('Python', 'C#', 'Javascript', 'Backend', 'Junior', 'Graduate', 'Software')
    location_checks = ('London', 'Oxford', 'Cambridge')
    # print(f'Subject: {any(i in message.subject for i in title_checks)}')
    # print(f'Location: {any(i in message.plain for i in location_checks)}')
    # print(f'Hybrid: {any(i in message.plain for i in work_type_checks)}')
    return any(i in message.subject for i in title_checks) or any(i in message.plain for i in location_checks)


def get_indeed_links(messages: list[Message]):
    href_pattern = r'<a\s+href=["\']([^"\']+)["\'].*?>\s*I\'m interested\s*</a>'
    res = [re.search(href_pattern, m.html) for m in messages]
    return [r.group(1) for r in res if r is not None]


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
            print(job.company, job.title, job.location)
    return



    indeed_messages = [m for m in messages if m.sender.split()[0] == "Indeed" and filter_indeed_message(m)]
    linkedin_messages = [m for m in messages if m.sender.split()[0] == "LinkedIn"]
    exec_messages = [m for m in messages if m.sender.split()[0] == "Executive"]
    cv_messages = [m for m in messages if m.sender.split()[0] == "CV-Library"]
    # print(len(messages))
    # print(len(linkedin_messages))
    # print(len(indeed_messages))
    # print(len(exec_messages))
    # print(len(cv_messages))
    
    # indeed_links = get_indeed_links(indeed_messages)
    # print(indeed_links)


if __name__ == '__main__':
    main()
