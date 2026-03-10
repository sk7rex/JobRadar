import pytest
from datetime import datetime
from src.job_radar.models.task import SearchTask, TaskStatus


def test_task_creation():
    """TC-MODEL-001: Создание задачи с минимальными параметрами"""
    task = SearchTask(keyword="python", source="habr")
    
    assert task.keyword == "python"
    assert task.source == "habr"
    assert task.status == TaskStatus.NEW
    assert task.id is None
    assert task.items_found == 0


def test_task_dates_auto_set():
    """TC-MODEL-002: Проверка автоматической установки дат"""
    task = SearchTask(keyword="python", source="habr")
    
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)
    
    # Проверка, что даты близки к текущему времени
    now = datetime.now()
    assert (now - task.created_at).seconds < 5


def test_task_status_enum():
    """Проверка всех значений enum TaskStatus"""
    assert TaskStatus.NEW.value == "new"
    assert TaskStatus.IN_PROGRESS.value == "in_progress"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled"
    assert TaskStatus.EXPIRED.value == "expired"
    assert TaskStatus.RETRIED.value == "retried"
