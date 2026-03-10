from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import inspect
from src.job_radar.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)


def init_db() -> str:
    """
    Инициализация базы данных.

    Возвращает:
    - "created" — если таблицы созданы
    - "exists" — если таблицы уже существуют
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if existing_tables:
        return "exists"

    SQLModel.metadata.create_all(engine)
    return "created"


def get_session():
    """Возвращает новую сессию."""
    return Session(engine)