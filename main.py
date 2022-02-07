import base64
import functools
import itertools
import random
import string
import json
import time
from datetime import date, datetime, timedelta
from typing import Optional, Generator
from urllib.request import urlopen, Request

from settings import *

try:
    from settings_local import *
except ImportError:
    pass


def make_dummy_cases(date_from: date) -> Generator[dict, None, None]:
    """
    Генератор тестовых обращений:

    Первому присваивается дата `date_from`.

    Второму - дата `date_from` + 1 день.
    Обращению `n` присваивается дата `date_from` + `n`, если эта дата
    не превосходит сегодняшнего числа. Иначе присваивание дат
    для этого номера и далее снова возвращается на дату `date_from`.

    Или: дата обращения i = date_from + ((i % (today - date_from + 1)) дней)
    """

    FIRST_NAMES = [
        'Alice',
        'Bob',
    ]

    LAST_NAMES = [
        'Brown',
        'Collins',
    ]

    EMAIL_HOSTS = [
        'gmail.com',
        'yahoo.com',
    ]

    today = date.today()

    for i in itertools.count():
        f_name = random.choice(FIRST_NAMES)
        l_name = random.choice(LAST_NAMES)

        year = random.randint(1960, 2004)
        email_host = random.choice(EMAIL_HOSTS)
        email = f'{f_name.lower()}.{l_name.lower()}{year}@{email_host}'

        phone = '+79' + ''.join(random.choice(string.digits) for _ in range(9))

        subject = f'Having trouble with form #{i}'
        content = f'Lorem ipsum #{i}'
        content_html = f'<span>{content}</span>'

        created_at_date = date_from + timedelta(days=i % ((today - date_from).days + 1))
        created_at = datetime.combine(created_at_date, datetime.min.time())

        yield {
            'user_email': email,
            'user_phone': phone,
            'user_whatsapp_phone': phone,
            'user_custom_id': email,
            'subject': subject,
            'content': content,
            'content_html': content_html,
            'created_at': str(created_at),
        }


def omni_request(path_without_slash: str, data: Optional[dict] = None) -> dict:
    url = f'https://{OMNIDESK_DOMAIN}.omnidesk.ru/api/{path_without_slash}'

    if not data:
        data_bytes = None
    else:
        data_json = json.dumps(data)
        data_bytes = data_json.encode('utf-8')

    req = Request(url, data=data_bytes, method='POST' if data else 'GET')
    req.add_header('Content-type', 'application/json')

    b64_auth_str = base64.b64encode(
        bytes(f'{OMNIDESK_EMAIL}:{OMNIDESK_API_KEY}', 'utf-8')
    ).decode('utf-8')
    req.add_header('Authorization', f'Basic {b64_auth_str}')

    with urlopen(req) as con:
        resp = con.read()
        return json.loads(resp.decode('utf-8'))


omni_request_cases = functools.partial(omni_request, 'cases.json')


def omni_post_dummy_cases(n: int, date_from: date, sleep_secs: int):
    cases = make_dummy_cases(date_from)
    for _ in range(n):
        new_case = next(cases)
        omni_request_cases(data={'case': new_case})
        time.sleep(sleep_secs)


if __name__ == '__main__':
    # примерно так можно создать тестовые обращения
    # omni_post_dummy_cases(200, date(2021, 12, 1), 1)
    omni_resp_data = omni_request('cases.json')
    print(omni_resp_data)
