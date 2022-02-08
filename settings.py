import pathlib

_project_abs_path = pathlib.Path(__file__).parent.resolve()

OMNIDESK_DOMAIN = 'example'
OMNIDESK_EMAIL = 'example@example.com'
OMNIDESK_API_KEY = 'EXAMPLE_API_KEY'
DATABASE_PATH = str(_project_abs_path / 'db.sqlite')
