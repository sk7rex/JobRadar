from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_FILE = BASE_DIR / "job_radar.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

HTML_STORAGE_DIR = BASE_DIR / "data" / "raw_html"
HTML_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SOURCES = [
    {"name": "habr", "url": "https://career.habr.com", "is_active": False},
    {"name": "hh", "url": "https://hh.ru", "is_active": False},
    {"name": "geekjob", "url": "https://geekjob.ru", "is_active": False},
    {"name": "superjob", "url": "https://superjob.ru/", "is_active": True}
]

# Crawler settings
MAX_PAGES = 14
HEADLESS = True
MIN_DELAY = 2.0
MAX_DELAY = 5.0
CARD_RETRIES = 1       # сколько раз повторить карточку при таймауте

# Description fetching (Phase 2: visit each vacancy page for full description)
FETCH_DESCRIPTIONS = True

# hh.ru area IDs (https://api.hh.ru/areas)
HH_CITY_IDS: dict[str, int] = {
    "москва": 1,
    "moscow": 1,
    "санкт-петербург": 2,
    "питер": 2,
    "спб": 2,
    "saint-petersburg": 2,
}
HH_DEFAULT_AREA = 113  # All Russia

# superjob.ru city IDs
SUPERJOB_CITY_IDS: dict[str, int] = {
    "москва": 4,
    "moscow": 4,
    "санкт-петербург": 14,
    "питер": 14,
    "спб": 14,
}
