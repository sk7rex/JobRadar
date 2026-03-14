import pytest
from datetime import datetime
from src.job_radar.models.task import SearchTask, TaskStatus


def test_task_creation():
    """TC-TASK-001: Создание задачи с минимальными параметрами"""
    task = SearchTask(
        source_id=1,
        keyword="python"
    )
    
    assert task.id is None
    assert task.source_id == 1
    assert task.keyword == "python"
    assert task.status == TaskStatus.NEW
    assert task.items_found == 0
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)


def test_task_with_custom_status():
    """TC-TASK-002: Создание задачи с указанием статуса"""
    task = SearchTask(
        source_id=1,
        keyword="java",
        status=TaskStatus.IN_PROGRESS,
        items_found=5
    )
    
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.items_found == 5


def test_task_status_enum():
    """TC-TASK-003: Проверка всех значений enum"""
    assert TaskStatus.NEW.value == "new"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled"
    assert TaskStatus.EXPIRED.value == "expired"
    assert TaskStatus.RETRIED.value == "retried"


def test_task_dates_auto_set():
    """TC-TASK-004: Проверка автоматической установки дат"""
    task = SearchTask(source_id=1, keyword="python")
    
    now = datetime.now()
    assert (now - task.created_at).seconds < 5
    assert (now - task.updated_at).seconds < 5


def test_task_source_relationship(session, test_source):
    """TC-TASK-005: Проверка связи задачи с источником"""
    # Создаем задачу, связанную с источником
    task = SearchTask(
        source_id=test_source.id,
        keyword="python"
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    # Проверяем, что связь работает
    assert task.source_relation is not None
    assert task.source_relation.name == test_source.name
    assert task.source_relation.url == test_source.url


def test_task_vacancies_relationship(session, test_task):
    """TC-TASK-006: Проверка связи задачи с вакансиями"""
    from src.job_radar.models.vacancy import Vacancy
    
    # Создаем вакансии для задачи
    vacancy1 = Vacancy(
        task_id=test_task.id,
        title="Python Developer",
        url="https://example.com/1"
    )
    vacancy2 = Vacancy(
        task_id=test_task.id,
        title="Senior Python",
        url="https://example.com/2"
    )
    session.add_all([vacancy1, vacancy2])
    session.commit()
    
    # Обновляем задачу, чтобы загрузить вакансии
    session.refresh(test_task)
    
    # Проверяем связь
    assert len(test_task.vacancies) == 2
    titles = [v.title for v in test_task.vacancies]
    assert "Python Developer" in titles
    assert "Senior Python" in titles


def test_task_logs_relationship(session, test_task):
    """TC-TASK-007: Проверка связи задачи с логами"""
    from src.job_radar.models.log import Log
    
    # Создаем логи для задачи
    log1 = Log(task_id=test_task.id, level="INFO", message="Task created")
    log2 = Log(task_id=test_task.id, level="INFO", message="Processing started")
    session.add_all([log1, log2])
    session.commit()
    
    # Обновляем задачу
    session.refresh(test_task)
    
    # Проверяем связь
    assert len(test_task.logs) == 2
    messages = [log.message for log in test_task.logs]
    assert "Task created" in messages
    assert "Processing started" in messages