from pathlib import Path

# Получаем путь к корню проекта (на 2 уровня выше этого файла)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_FILE = BASE_DIR / "job_radar.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Разрешенные источники (можно легко добавить новые)
ALLOWED_SOURCES = {"habr", "hh", "geekjob", "linkedin"}