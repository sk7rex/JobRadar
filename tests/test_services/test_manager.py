import pytest
from sqlmodel import select
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.services.manager import TaskManager
from src.job_radar.config import ALLOWED_SOURCES


def test_create_valid_task(manager, session, sample_task_data):
    """TC-MANAGER-001: Успешное создание задачи"""
    task = manager.create_task(
        sample_task_data["keyword"], 
        sample_task_data["source"]
    )
    
    assert task.id is not None
    assert task.keyword == sample_task_data["keyword"]
    assert task.source == sample_task_data["source"]
    assert task.status == TaskStatus.NEW
    
    # Проверка сохранения в БД
    db_task = session.get(SearchTask, task.id)
    assert db_task is not None
    assert db_task.keyword == "python"


def test_create_task_invalid_source(manager):
    """TC-MANAGER-002: Создание задачи с недопустимым источником"""
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("python", "invalid_source")
    
    assert "Источник 'invalid_source' недоступен" in str(exc_info.value)
    assert all(src in str(exc_info.value) for src in ALLOWED_SOURCES)


def test_create_duplicate_task(manager, session):
    """TC-MANAGER-003: Создание дубликата активной задачи"""
    # Создаем первую задачу
    task1 = manager.create_task("python", "habr")
    
    # Пытаемся создать дубликат
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("python", "habr")
    
    assert "Такая задача уже в работе" in str(exc_info.value)
    assert str(task1.id) in str(exc_info.value)


def test_create_task_case_insensitive(manager):
    """Проверка приведения к нижнему регистру"""
    task = manager.create_task("Python Developer", "HABR")
    
    assert task.keyword == "python developer"
    assert task.source == "habr"


def test_list_tasks_empty(manager):
    """TC-MANAGER-004: Получение списка из пустой БД"""
    tasks = manager.list_tasks()
    assert tasks == []


def test_list_tasks_with_limit(manager, session):
    """TC-MANAGER-005: Проверка лимита при получении списка"""
    # Создаем 15 задач
    for i in range(15):
        task = SearchTask(keyword=f"python{i}", source="habr")
        session.add(task)
    session.commit()
    
    # Проверка с разными лимитами
    assert len(manager.list_tasks(limit=5)) == 5
    assert len(manager.list_tasks(limit=10)) == 10
    assert len(manager.list_tasks(limit=20)) == 15


def test_list_tasks_order(manager, session):
    """Проверка сортировки по дате создания"""
    # Создаем задачи с небольшими задержками
    import time
    
    task1 = SearchTask(keyword="first", source="habr")
    session.add(task1)
    session.commit()
    time.sleep(0.1)
    
    task2 = SearchTask(keyword="second", source="habr")
    session.add(task2)
    session.commit()
    
    tasks = manager.list_tasks(limit=2)
    assert tasks[0].keyword == "second"  # Последняя созданная первой в списке
    assert tasks[1].keyword == "first"
