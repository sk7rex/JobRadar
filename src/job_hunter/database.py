from sqlmodel import SQLModel, create_engine, Session
from src.job_hunter.config import DATABASE_URL

# check_same_thread=False нужен для SQLite
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
    """Создает таблицы в базе данных."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Возвращает новую сессию."""
    return Session(engine)