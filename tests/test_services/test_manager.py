import pytest
from sqlmodel import select
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.source import Source
from src.job_radar.models.log import Log
from src.job_radar.models.vacancy import Vacancy


def test_create_valid_task(manager, session, test_source):
    """TC-MANAGER-001: Успешное создание задачи"""
    task = manager.create_task("python", test_source.name)
    
    assert task.id is not None
    assert task.keyword == "python"
    assert task.source_id == test_source.id
    assert task.status == TaskStatus.NEW
    
    # Проверка создания лога
    logs = session.exec(select(Log).where(Log.task_id == task.id)).all()
    assert len(logs) == 1
    assert logs[0].level == "INFO"


def test_create_task_invalid_source(manager):
    """TC-MANAGER-002: Создание задачи с несуществующим источником"""
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("python", "invalid_source")
    
    assert "не найден" in str(exc_info.value)


def test_create_task_inactive_source(manager, session, test_source):
    """TC-MANAGER-003: Создание задачи с неактивным источником"""
    # Деактивируем источник
    test_source.is_active = False
    session.add(test_source)
    session.commit()
    
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("python", test_source.name)
    
    assert "отключен" in str(exc_info.value)


def test_create_duplicate_task(manager, test_source):
    """TC-MANAGER-004: Создание дубликата активной задачи"""
    task1 = manager.create_task("python", test_source.name)
    
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("python", test_source.name)
    
    assert "уже в работе" in str(exc_info.value)
    assert str(task1.id) in str(exc_info.value)


def test_create_task_empty_keyword(manager, test_source):
    """TC-MANAGER-005: Создание задачи с пустым ключевым словом"""
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("", test_source.name)
    
    assert "не может быть пустым" in str(exc_info.value)


def test_list_tasks(manager, session, test_source, another_source):
    """TC-MANAGER-006: Проверка списка задач"""
    # Создаем задачи
    task1 = manager.create_task("python", test_source.name)
    task2 = manager.create_task("java", another_source.name)
    
    tasks = manager.list_tasks(limit=10)
    assert len(tasks) == 2
    assert tasks[0].keyword == "java"  # последняя созданная


def test_delete_task(manager, session, test_source):
    """TC-MANAGER-007: Удаление задачи"""
    task = manager.create_task("python", test_source.name)
    task_id = task.id
    
    # Удаляем
    result = manager.delete_task(task_id)
    assert result is True
    
    # Проверяем, что задача удалена
    deleted_task = session.get(SearchTask, task_id)
    assert deleted_task is None


def test_add_source(manager, session):
    """TC-MANAGER-008: Добавление нового источника"""
    source = manager.add_source("new_source", "https://new.com")
    
    assert source.id is not None
    assert source.name == "new_source"
    assert source.url == "https://new.com"
    assert source.is_active is True


def test_add_duplicate_source(manager, test_source):
    """TC-MANAGER-009: Добавление дубликата источника"""
    with pytest.raises(ValueError) as exc_info:
        manager.add_source(test_source.name, "https://any.com")
    
    assert "уже существует" in str(exc_info.value)


def test_delete_source(manager, test_source):
    """TC-MANAGER-010: Удаление источника без задач"""
    result = manager.delete_source(test_source.name)
    assert result is True


def test_delete_source_with_tasks(manager, session, test_source):
    """TC-MANAGER-011: Попытка удалить источник с задачами"""
    # Создаем задачу
    manager.create_task("python", test_source.name)
    
    with pytest.raises(ValueError) as exc_info:
        manager.delete_source(test_source.name)
    
    assert "привязаны задачи" in str(exc_info.value)


def test_list_sources(manager, test_source, another_source):
    """TC-MANAGER-012: Список источников"""
    sources = manager.list_sources()
    assert len(sources) >= 2
    source_names = [s.name for s in sources]
    assert "habr" in source_names
    assert "hh" in source_names


def test_list_vacancies(manager, session, test_task):
    """TC-MANAGER-013: Список вакансий"""
    from src.job_radar.models.vacancy import Vacancy
    
    # Создаем тестовые вакансии
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
    
    vacancies = manager.list_vacancies(limit=10)
    assert len(vacancies) >= 2
    titles = [v.title for v in vacancies]
    assert "Python Developer" in titles
    assert "Senior Python" in titles


def test_list_logs(manager, session, test_task):
    """TC-MANAGER-014: Список логов"""
    # Создаем тестовый лог
    log = Log(
        task_id=test_task.id,
        level="INFO",
        message="Test log"
    )
    session.add(log)
    session.commit()
    
    logs = manager.list_logs(limit=10)
    assert len(logs) >= 1
    assert logs[0].message == "Test log"


def test_toggle_source_active(manager, session, test_source):
    """TC-MANAGER-015: Включение/выключение источника"""
    # Сейчас источник активен (is_active=True)
    
    # Деактивируем
    test_source.is_active = False
    session.add(test_source)
    session.commit()
    
    # Пытаемся создать задачу с неактивным источником
    with pytest.raises(ValueError) as exc_info:
        manager.create_task("python", test_source.name)
    
    assert "отключен" in str(exc_info.value)
    
    # Реактивируем
    test_source.is_active = True
    session.add(test_source)
    session.commit()
    
    # Теперь задача должна создаться
    task = manager.create_task("python", test_source.name)
    assert task is not None