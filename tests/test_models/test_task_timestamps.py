import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.source import Source


def test_updated_at_auto_updates_on_change(session, test_source):
    """
    TC-TASK-UPD-001: Проверка, что updated_at автоматически обновляется при изменении задачи.
    
    Этот тест проверяет, что поле updated_at ведёт себя как "время последнего изменения":
    - При создании = времени создания
    - При изменении = новому времени
    """
    # 1. СОЗДАЁМ задачу
    task = SearchTask(
        source_id=test_source.id,
        keyword="python",
        status=TaskStatus.NEW
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    # Запоминаем время создания
    created_time = task.created_at
    first_updated = task.updated_at
    
    print(f"\n Задача создана:")
    print(f"   created_at: {created_time}")
    print(f"   updated_at: {first_updated}")
    
    # Проверяем, что created_at и updated_at примерно равны (разница < 1 сек)
    assert abs((created_time - first_updated).total_seconds()) < 1, \
        "При создании updated_at должен быть близок к created_at"
    
    # 2. Ждём немного, чтобы время изменилось
    import time
    time.sleep(0.1)
    
    # 3. ИЗМЕНЯЕМ задачу
    task.status = TaskStatus.IN_PROGRESS
    task.items_found = 5
    session.add(task)
    session.commit()
    session.refresh(task)
    
    new_updated = task.updated_at
    
    print(f"\n После изменения:")
    print(f"   status: {task.status}")
    print(f"   items_found: {task.items_found}")
    print(f"   new updated_at: {new_updated}")
    
    # 4. ПРОВЕРЯЕМ, что updated_at увеличился
    assert new_updated > first_updated, \
        f"updated_at должен увеличиться при изменении задачи: {first_updated} -> {new_updated}"
    
    # 5. Проверяем, что created_at НЕ изменился
    assert task.created_at == created_time, \
        "created_at НЕ должен меняться при обновлении задачи"


def test_updated_at_stays_same_if_no_changes(session, test_source):
    """
    TC-TASK-UPD-002: Проверка, что updated_at НЕ меняется, если нет реальных изменений.
    """
    # Создаём задачу
    task = SearchTask(
        source_id=test_source.id,
        keyword="python",
        status=TaskStatus.NEW
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    first_updated = task.updated_at
    
    # Ждём
    import time
    time.sleep(0.1)
    
    # "Изменяем" на то же самое значение
    task.status = TaskStatus.NEW  # тот же статус!
    session.add(task)
    session.commit()
    session.refresh(task)
    
    # updated_at НЕ должно измениться
    assert task.updated_at == first_updated, \
        "updated_at не должен меняться при изменении на то же значение"


def test_updated_at_multiple_changes(session, test_source):
    """
    TC-TASK-UPD-003: Проверка, что updated_at обновляется при каждом изменении.
    """
    task = SearchTask(
        source_id=test_source.id,
        keyword="python",
        status=TaskStatus.NEW
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    timestamps = [task.updated_at]
    
    # Несколько изменений
    changes = [
        (TaskStatus.IN_PROGRESS, "в работу"),
        (TaskStatus.COMPLETED, "завершено"),
        (TaskStatus.FAILED, "ошибка")
    ]
    
    for new_status, description in changes:
        import time
        time.sleep(0.1)
        
        task.status = new_status
        session.add(task)
        session.commit()
        session.refresh(task)
        
        timestamps.append(task.updated_at)
        print(f"\n После изменения на {description}: {task.updated_at}")
    
    # Проверяем, что каждый раз время увеличивалось
    for i in range(1, len(timestamps)):
        assert timestamps[i] > timestamps[i-1], \
            f"На шаге {i} время должно увеличиться: {timestamps[i-1]} -> {timestamps[i]}"