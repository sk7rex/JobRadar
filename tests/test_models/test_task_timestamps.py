import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.source import Source
from src.job_radar.cli.app import app
from src.job_radar.services.manager import TaskManager

def test_updated_at_stays_same_if_no_changes(session, test_source):
    """
    TC-TASK-UPD-002: Проверка, что updated_at НЕ меняется, если нет реальных изменений.
    """
    manager = TaskManager(session)
    
    # Создаём задачу
    task = manager.create_task("testpython", test_source.name)
    first_updated = task.updated_at
    
    # Ждём немного, чтобы время точно могло измениться
    import time
    time.sleep(0.1)
    
    # Пытаемся "изменить" на тот же статус
    # (update_task_status должен проверять, меняется ли статус реально)
    task = manager.update_task_status(task.id, TaskStatus.NEW)  # тот же статус!
    
    # updated_at НЕ должно измениться
    assert task.updated_at == first_updated, \
        "updated_at не должен меняться при изменении на то же значение"


def test_updated_at_multiple_changes(session, test_source):
    """
    TC-TASK-UPD-003: Проверка, что updated_at обновляется при каждом изменении.
    """
    manager = TaskManager(session)
    
    
    task = manager.create_task("testpython", test_source.name)
    timestamps = [task.updated_at]
    
    statuses = [
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED
    ]
    
    for new_status in statuses:
        import time
        time.sleep(0.1)
        task = manager.update_task_status(task.id, new_status)
        timestamps.append(task.updated_at)
        print(f"\n Статус: {new_status.value}, updated_at: {task.updated_at}")
    
    # Проверяем увеличение времени
    for i in range(1, len(timestamps)):
        assert timestamps[i] > timestamps[i-1], \
            f"На шаге {i} время должно увеличиться: {timestamps[i-1]} -> {timestamps[i]}"
    
