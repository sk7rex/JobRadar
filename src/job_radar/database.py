from sqlalchemy import inspect
from sqlmodel import SQLModel, create_engine, Session, select

from src.job_radar.config import DATABASE_URL, DEFAULT_SOURCES
# Импортируем модели, чтобы SQLModel знал о них при создании таблиц (create_all)
from src.job_radar.models.source import Source

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)


def seed_sources(session: Session):
    """
    Наполняет таблицу источников базовыми значениями, если она пуста.
    """
    existing_source = session.exec(select(Source)).first()
    if not existing_source:
        for src_data in DEFAULT_SOURCES:
            source = Source(**src_data)
            session.add(source)
        session.commit()
        return True
    return False


def init_db() -> str:
    """
    Инициализация базы данных.
    
    Возвращает:
    - "created" — если таблицы созданы (и источники добавлены)
    - "exists" — если таблицы уже существуют
    """
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if not existing_tables:
        SQLModel.metadata.create_all(engine)

        # Сразу наполняем справочник источников
        with Session(engine) as session:
            seed_sources(session)

        return "created"

    return "exists"


def get_session():
    """Возвращает новую сессию."""
    return Session(engine)
