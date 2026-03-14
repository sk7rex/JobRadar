import pytest
import tempfile
import os
from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy import event, inspect
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.log import Log
from src.job_radar.models.vacancy import Vacancy
from src.job_radar.config import DEFAULT_SOURCES


@pytest.fixture(scope="session")
def test_engine():

    """Создает временную БД для тестов с источниками по умолчанию"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    test_engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(test_engine)
    
    # Добавляем источники по умолчанию (как в реальном приложении)
    with Session(test_engine) as session:
        for src_data in DEFAULT_SOURCES:
            # Проверяем, нет ли уже такого источника
            existing = session.exec(
                select(Source).where(Source.name == src_data["name"])
            ).first()
            if not existing:
                source = Source(**src_data)
                session.add(source)
        session.commit()
    
    yield test_engine
    
    test_engine.dispose()
    try:
        os.unlink(db_path)
    except PermissionError:
        print(f"Не удалось удалить временный файл {db_path}: {e}")


@pytest.fixture
def session(test_engine):
    """
    Фикстура сессии с транзакциями.
    Каждый тест получает свою транзакцию, которая откатывается после теста.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    
    session = Session(bind=connection)
    
    yield session
    
    transaction.rollback()
    session.close()
    connection.close()


@pytest.fixture
def manager(session):
    """Фикстура для TaskManager"""
    from src.job_radar.services.manager import TaskManager
    return TaskManager(session)


@pytest.fixture
def test_source(session):
    """Возвращает существующий источник habr (не создает новый)"""
    from sqlmodel import select
    
    source = session.exec(
        select(Source).where(Source.name == "habr")
    ).first()
    
    if not source:
        source = Source(name="habr", url="https://habr.com", is_active=True)
        session.add(source)
        session.commit()
        session.refresh(source)
    
    return source


@pytest.fixture
def another_source(session):
    """Возвращает существующий источник hh"""
    from sqlmodel import select
    
    source = session.exec(
        select(Source).where(Source.name == "hh")
    ).first()
    
    if not source:
        source = Source(name="hh", url="https://hh.ru", is_active=True)
        session.add(source)
        session.commit()
        session.refresh(source)
    
    return source


@pytest.fixture
def test_task(session, test_source):
    """Создает тестовую задачу"""
    from src.job_radar.models.task import SearchTask, TaskStatus
    
    task = SearchTask(
        source_id=test_source.id,
        keyword="python",
        status=TaskStatus.NEW
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@pytest.fixture
def test_vacancy(session, test_task):
    """Создает тестовую вакансию"""
    from src.job_radar.models.vacancy import Vacancy
    
    vacancy = Vacancy(
        task_id=test_task.id,
        title="Python Developer",
        url="https://example.com/vacancy/1"
    )
    session.add(vacancy)
    session.commit()
    session.refresh(vacancy)
    return vacancy


@pytest.fixture
def test_log(session, test_task):
    """Создает тестовый лог"""
    from src.job_radar.models.log import Log
    
    log = Log(
        task_id=test_task.id,
        level="INFO",
        message="Test log message"
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log