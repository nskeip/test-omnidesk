import itertools
import random
import string
from datetime import datetime, timedelta

from settings import *

try:
    from settings_local import *
except ImportError:
    pass


def make_dummy_cases(since: datetime):
    """
    Генератор тестовых обращений:

    Первому присваивается дата `since`.

    Второму - дата `since` + 1 день.
    Обращению `n` присваивается дата `since` + `n`, если эта дата
    не превосходит сегодняшнего числа. Иначе присваивание дат
    для этого номера и далее снова возвращается на дату `since`.

    Или: дата обращения i = since + ((i % (now - since + 1)) дней)
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

    now = datetime.now()

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

        created_at = since + timedelta(days=i % ((now - since).days + 1))

        yield {
            'email': email,
            'phone': phone,
            'user_whatsapp_phone': phone,
            'user_custom_id': email,
            'subject': subject,
            'content': content,
            'content_html': content_html,
            'created_at': created_at.timestamp(),
        }


if __name__ == '__main__':
    pass
