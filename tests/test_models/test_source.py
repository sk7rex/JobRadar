import pytest
from sqlmodel import select
from src.job_radar.models.source import Source


def test_source_creation():
    """TC-SOURCE-001: Создание источника с минимальными параметрами"""
    source = Source(
        name="habr",
        url="https://habr.com"
    )
    
    assert source.id is None
    assert source.name == "habr"
    assert source.url == "https://habr.com"
    assert source.is_active is True  # значение по умолчанию
    assert source.tasks == []  # пустой список задач


def test_source_with_custom_active():
    """TC-SOURCE-002: Создание неактивного источника"""
    source = Source(
        name="old_site",
        url="https://old.com",
        is_active=False
    )
    
    assert source.is_active is False

@pytest.mark.filterwarnings("ignore:.*transaction already deassociated.*")
# т.к. когда commit() падает, связанная с ним транзакция автоматически завершается, и
# после выхода из теста фикстура session пытается выполнить rollback()
def test_source_name_uniqueness(session):
    """TC-SOURCE-003: Проверка уникальности имени источника"""
    # Пытаемся создать дубликат существующего источника
    source = Source(name="habr", url="https://habr.com")
    session.add(source)
    
    with pytest.raises(Exception) as excinfo:
        session.commit()
    
    # Проверяем, что это именно ошибка уникальности
    assert "UNIQUE constraint failed" in str(excinfo.value)
    assert "sources.name" in str(excinfo.value)


def test_source_tasks_relationship(session, test_source, test_task):
    """TC-SOURCE-005: Проверка связи источника с задачами"""
    # test_task уже должна быть создана с этим источником
    session.refresh(test_source)
    
    # Проверяем, что у источника есть наша задача
    assert len(test_source.tasks) >= 1
    assert test_source.tasks[0].keyword == "python"  # или что там в test_task