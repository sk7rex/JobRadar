from pathlib import Path

# Получаем путь к корню проекта (на 3 уровня выше этого файла)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_FILE = BASE_DIR / "job_radar.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Начальные данные для заполнения таблицы Sources (сидинг)
DEFAULT_SOURCES = [
    {"name": "habr", "url": "https://career.habr.com", "is_active": True},
    {"name": "hh", "url": "https://hh.ru", "is_active": True},
    {"name": "geekjob", "url": "https://geekjob.ru", "is_active": True},
]