import pytest
import tempfile
import os
import time
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine

# Добавляем корневую директорию в путь
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_radar.database import engine as main_engine
from src.job_radar.config import DATABASE_URL


@pytest.fixture
def temp_db():
    """Создает временную БД для тестов с правильным закрытием"""
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Создаем engine с правильными настройками
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_size=1,  # Ограничиваем пул соединений
        max_overflow=0
    )
    
    # Создаем таблицы
    SQLModel.metadata.create_all(test_engine)
    
    # Отдаем engine тестам
    yield test_engine
    
    # ВАЖНО: Явно закрываем все соединения
    test_engine.dispose()
    
    # Даем время на закрытие
    time.sleep(0.1)
    
    # Пробуем удалить файл (с повторными попытками)
    for attempt in range(3):
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
            break  # Успешно удалили
        except PermissionError:
            if attempt == 2:  # Последняя попытка
                print(f"⚠ Не удалось удалить {db_path}")
                # Не падаем, просто логируем
            else:
                time.sleep(0.1)  # Ждем и пробуем снова


@pytest.fixture
def session(temp_db):
    """Фикстура для сессии БД с автоматическим закрытием"""
    with Session(temp_db) as session:
        yield session
    # Сессия автоматически закрывается при выходе из with


@pytest.fixture
def manager(session):
    """Фикстура для TaskManager"""
    from src.job_radar.services.manager import TaskManager
    return TaskManager(session)


@pytest.fixture
def sample_task_data():
    """Образец данных для задачи"""
    return {
        "keyword": "python",
        "source": "habr"
    }