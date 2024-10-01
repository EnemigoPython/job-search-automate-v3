import re
from simplegmail import Gmail
from simplegmail.message import Message
from simplegmail.query import construct_query

# HREF_PATTERN = r'href\s*=\s*["\']?([^"\'\s>]+)'
# HREF_PATTERN = r'href\s*=\s*["\']?([^"\'\s>]+)["\']?\s*>(?:\s*)I\'m interested'
HREF_PATTERN = r'<a\s+href=["\']([^"\']+)["\'].*?>\s*I\'m interested\s*</a>'


def init_gmail_client():
    return Gmail(client_secret_file="credentials.json")


def get_job_alert_mail(gmail: Gmail):

    indeed_params = {
        'sender': 'invitetoapply@indeed.com',
        'newer_than': (5, "day"),
        # 'unread': True
    }
    linkedin_params = {
        'sender': 'jobs-noreply@linkedin.com',
        'newer_than': (5, "day")
    }
    messages = gmail.get_messages(query=construct_query(
        indeed_params,
        linkedin_params
    ))
    print(messages)
    return messages


def filter_indeed_message(message: Message):
    '''
    Attempt to filter for only jobs that we should bother applying for
    '''
    title_checks = ('Python', 'C#', 'Javascript', 'Backend', 'Junior', 'Graduate')
    location_checks = ('London', 'Oxford', 'Cambridge')
    # print(f'Subject: {any(i in message.subject for i in title_checks)}')
    # print(f'Location: {any(i in message.plain for i in location_checks)}')
    # print(f'Hybrid: {any(i in message.plain for i in work_type_checks)}')
    return any(i in message.subject for i in title_checks) or any(i in message.plain for i in location_checks)


def get_indeed_links(messages: list[Message]):
    href_pattern = r'<a\s+href=["\']([^"\']+)["\'].*?>\s*I\'m interested\s*</a>'
    res = [re.search(href_pattern, m.html) for m in messages]
    return [r.group(1) for r in res if r is not None]


def get_linkedin_links(messages: list[Message]):
    href_pattern = r'https://www\.linkedin\.com/comm/jobs/view/\S+'
    res = [re.findall(href_pattern, m.html) for m in messages]
    return res


def main():
    gmail = init_gmail_client()
    messages = get_job_alert_mail(gmail)
    indeed_messages = [m for m in messages if m.sender.split()[0] == "Indeed" and filter_indeed_message(m)]
    linkedin_messages = [m for m in messages if m.sender.split()[0] == "LinkedIn"]
    indeed_links = get_indeed_links(indeed_messages)
    print(indeed_links)
    linkedin_links = get_linkedin_links(linkedin_messages)
    print(linkedin_links)


if __name__ == '__main__':
    main()
