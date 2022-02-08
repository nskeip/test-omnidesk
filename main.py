import base64
import itertools
import math
import random
import string
import json
import time
from datetime import date, datetime, timedelta
from typing import Optional, List
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from settings import *

CASES_PATH = 'cases.json'
ITEMS_PER_PAGE = 100

try:
    from settings_local import *
except ImportError:
    pass


def make_dummy_cases(date_from: date, date_until: date, n_each_day: int) -> List[dict]:
    """
    Сделать список тестовых обращений для загрузки в Omnidesk.

        :param date_from: начало периода (включительно)
        :param date_until: конец периода (не включительно)
        :param n_each_day: количество обращений в день
        :returns: список тестовых обращений

    """
    assert date_from < date_until

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

    dates_of_cases = itertools.takewhile(
        lambda d: d < date_until,
        (date_from + timedelta(days=d) for d in itertools.count()),
    )

    results = []

    for i, (created_at_date, _) in enumerate(
        itertools.product(dates_of_cases, range(n_each_day))
    ):
        f_name = random.choice(FIRST_NAMES)
        l_name = random.choice(LAST_NAMES)

        year = random.randint(1960, 2004)
        email_host = random.choice(EMAIL_HOSTS)
        email = f'{f_name.lower()}.{l_name.lower()}{year}@{email_host}'

        phone = '+79' + ''.join(random.choice(string.digits) for _ in range(9))

        subject = f'Having trouble with form #{i}'
        content = f'Lorem ipsum #{i}'
        content_html = f'<span>{content}</span>'

        created_at = datetime.combine(created_at_date, datetime.min.time())

        results.append(
            {
                'user_email': email,
                'user_phone': phone,
                'user_whatsapp_phone': phone,
                'user_custom_id': email,
                'subject': subject,
                'content': content,
                'content_html': content_html,
                'created_at': str(created_at),
            }
        )

    return results


def omni_request(path_without_slash: str, data: Optional[dict] = None) -> dict:
    url = f'https://{OMNIDESK_DOMAIN}.omnidesk.ru/api/{path_without_slash}'

    if not data:
        data_bytes = None
    else:
        data_json = json.dumps(data)
        data_bytes = data_json.encode('utf-8')

    req = Request(url, data=data_bytes)
    req.add_header('Content-type', 'application/json')

    b64_auth_str = base64.b64encode(
        bytes(f'{OMNIDESK_EMAIL}:{OMNIDESK_API_KEY}', 'utf-8')
    ).decode('utf-8')
    req.add_header('Authorization', f'Basic {b64_auth_str}')

    with urlopen(req) as con:
        resp = con.read()
        return json.loads(resp.decode('utf-8'))


def omni_post_dummy_cases(
    date_from: date, date_until: date, n_each_day: int, sleep_secs: int
):
    for new_case in make_dummy_cases(date_from, date_until, n_each_day):
        omni_request(CASES_PATH, data={'case': new_case})
        time.sleep(sleep_secs)


def omni_load_cases(date_from: date) -> List[dict]:
    """
    Загружает из Omnidesk обращения, начиная с даты from_date.
    Учитывает пагинацию и склеивает ответы в один список.
    Главная функция нашего скрипта.

    :param date_from:
    :return: список словарей, полученных от Omnidesk
    """
    result = []

    next_page_number = 0

    while True:  # потому что нет do-while
        params = {
            'page': next_page_number,
            'from_time': str(date_from),
        }
        url_params = urlencode(params)
        url = f'{CASES_PATH}?{url_params}'
        cases_data = omni_request(url)

        result += [v['case'] for k, v in cases_data.items() if k.isdigit()]

        # обновляем информацию о количестве загружаемых страниц,
        # так как число обращений может измениться во время работы скрипта
        total_count = cases_data.get('total_count', 1)
        pages_needed = math.ceil(total_count / ITEMS_PER_PAGE)

        next_page_number += 1
        if next_page_number < pages_needed:
            time.sleep(0.5)  # небольшой лаг перед следующим запросом
        else:
            break

    return result


if __name__ == '__main__':
    # Примерно так можно создать тестовые обращения
    # omni_post_dummy_cases(date(2021, 12, 1), date(2022, 2, 5), 3, 1)

    omni_cases = omni_load_cases(date(2022, 2, 6))
    print(omni_cases)
    pass
