# ===== FILE: config.py =====
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_FILE = BASE_DIR / "job_radar.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Папка для сохранения сырых HTML файлов
HTML_STORAGE_DIR = BASE_DIR / "data" / "raw_html"
HTML_STORAGE_DIR.mkdir(parents=True, exist_ok=True) # Создаст папку, если её нет

DEFAULT_SOURCES = [
    {"name": "habr", "url": "https://career.habr.com", "is_active": True},
    {"name": "hh", "url": "https://hh.ru", "is_active": True},
    {"name": "geekjob", "url": "https://geekjob.ru", "is_active": True},
]