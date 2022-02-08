import argparse
import base64
import copy
import itertools
import math
import random
import string
import json
import time
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional, List
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from settings import *

try:
    from settings_local import *
except ImportError:
    pass


# region EXCEPTIONS
class OmnideskApiOutdated(Exception):
    pass


# endregion

# region DUMMY CASES HELPER
def make_dummy_cases(date_from: date, date_until: date, n_each_day: int) -> List[dict]:
    """
    Сделать список тестовых обращений для загрузки в Omnidesk.

        :param date_from: начало периода (включительно)
        :param date_until: конец периода (не включительно)
        :param n_each_day: количество обращений в день
        :returns: список тестовых обращений

    Примерно так можно создать тестовые обращения:
    omni_post_dummy_cases(date(2021, 12, 1), date(2022, 2, 5), 3, 1)
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


# endregion

# region OMNI API FUNCTIONS
CASES_PATH = 'cases.json'
ITEMS_PER_PAGE = 100


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

        try:

            result += [v['case'] for k, v in cases_data.items() if k.isdigit()]

            # обновляем информацию о количестве загружаемых страниц,
            # так как число обращений может измениться во время работы скрипта
            total_count = cases_data['total_count']
            assert isinstance(total_count, int)
        except (
            KeyError,
            AssertionError,
        ):
            raise OmnideskApiOutdated()

        pages_needed = math.ceil(total_count / ITEMS_PER_PAGE)

        next_page_number += 1
        if next_page_number < pages_needed:
            time.sleep(0.5)  # небольшой лаг перед следующим запросом
        else:
            break

    return result


# endregion

# region DB FUNCTIONS
def create_db_tables_if_not_exist(con: sqlite3.Connection):
    script = """
        create table if not exists cases
        (
            id  integer not null constraint cases_pk
                primary key autoincrement,
            omni_case_id integer not null,
            case_number text,
            subject text default '' not null,
            user_id integer,
            staff_id integer,
            group_id integer,
            status text,
            priority text default '' not null,
            channel text,
            recipient text default '' not null,
            cc_emails text default '' not null,
            bcc_emails text default '' not null,
            deleted integer,
            spam integer,
            created_at integer,
            closed_at integer,
            updated_at integer,
            last_response_at integer,
            parent_case_id integer,
            closing_speed integer,
            language_id integer
        );
        
        create unique index if not exists cases_omni_case_id_uindex on cases (omni_case_id);
        
        """
    cur = con.cursor()
    cur.executescript(script)
    cur.close()


def upsert_without_commit(con: sqlite3.Connection, case: dict):
    """
    Добавляет или обновляет выгруженное обращение в бд

    :param con: соединение sqlite
    :param case: словарь, один из списка, возвращенного omni_load_cases
    :return:
    """

    def _db_friendly_copy(d):
        copy_of_d = copy.deepcopy(d)
        copy_of_d['omni_case_id'] = d['case_id']
        del copy_of_d['case_id']
        return copy_of_d

    # делаем shadow, чтобы избежать перезаписи
    case = _db_friendly_copy(case)  # noqa

    columns = [
        'omni_case_id',
        'case_number',
        'subject',
        'user_id',
        'staff_id',
        'group_id',
        'status',
        'priority',
        'channel',
        'recipient',
        'cc_emails',
        'bcc_emails',
        'deleted',
        'spam',
        'created_at',
        'closed_at',
        'updated_at',
        'last_response_at',
        'parent_case_id',
        'closing_speed',
        'language_id',
    ]

    values_placeholder_for_insert = ','.join(f':{c}' for c in columns)
    insert_pattern = f"insert into cases ({','.join(columns)}) values ({values_placeholder_for_insert})"

    kv_placeholder_for_update = ','.join(f'{c}=:{c}' for c in columns)
    nested_update_pattern = f'update set {kv_placeholder_for_update}'

    query_pattern = (
        f'{insert_pattern} on conflict(omni_case_id) do {nested_update_pattern}'
    )

    con.cursor().execute(query_pattern, case)


# endregion


# region DATE FUNCTIONS


def find_date_number_a_month_ago(some_date: date):
    """
    Найти дату "месяц назад".

    В простом случае - это просто "31 день назад",
    но так как количество дней месяцев не одинаково,
    то 31 день назад может быть другое число месяца.
    Поэтому мы ищем дату в предыдущем месяце,
    число которой совпадает с текущим числом.
    Если такой даты нет (например, в соответствие
    дате 31 марта мы не можем поставить "31" февраля),
    то мы берем максимальную дату предыдущего месяца.


    31 января 2022 года -> 31 декабря 2021 года
    31 марта 2020 года -> 29 февраля 2022 года
    31 марта 2022 года -> 28 февраля 2022 года
    """
    # считаем максимальное число предыдущего месяца
    last_day_of_prev_month = some_date.replace(day=1) - timedelta(days=1)
    return next(
        itertools.chain(
            itertools.dropwhile(  # пытаемся вычитать 28, 29, 30, 31 день
                lambda d: d.day != some_date.day,
                ((some_date - timedelta(days=i)) for i in range(28, 32)),
            ),
            [last_day_of_prev_month],  # ...если с вычитанием не получилось
        )
    )


# endregion


def run(date_from=None, database_path=DATABASE_PATH):
    with sqlite3.connect(database_path) as con:
        con.row_factory = sqlite3.Row

        create_db_tables_if_not_exist(con)

        omni_cases = omni_load_cases(date_from)
        for case in omni_cases:
            upsert_without_commit(con, case)
        con.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=f'python3 {__file__}', add_help=False)
    parser.add_argument(
        '-h',
        '--help',
        help='Вывести это сообщение-подсказку и ничего не загружать',
        action='help',
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        '--from_date',
        help='Начало периода, в формате ГГГГ-ММ-ДД (например, 2020-12-31)',
    )
    args = parser.parse_args()

    if args.from_date:
        try:
            from_date = datetime.strptime(args.from_date, '%Y-%m-%d').date()
        except ValueError:
            print('Неверный формат даты. Верный формат: ГГГГ-ММ-ДД')
            exit(1)
    else:
        # ищем в предыдущем месяце такое же число, как у сегодняшнего дня
        today = date.today()
        from_date = find_date_number_a_month_ago(today)

    try:
        print(f'Загрузка данных, начиная с {from_date}')  # noqa
        run(date_from=from_date)
    except URLError:
        print('Не удается установить соединение с omnidesk.')
    except OmnideskApiOutdated:
        print(
            'Похоже, вы пользуетесь устаревшей версией API Omnidesk. '
            'Обратитесь к разработчику для обновления скрипта.'
        )
    except sqlite3.Error:
        print('Ошибка записи в базу данных.')

    print('Готово')
