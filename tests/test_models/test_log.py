import pytest
from datetime import datetime
from src.job_radar.models.log import Log


def test_log_creation():
    """TC-LOG-001: Создание лога с минимальными параметрами"""
    log = Log(
        task_id=1,
        message="Тестовое сообщение"
    )
    
    assert log.id is None
    assert log.task_id == 1
    assert log.level == "INFO"  # значение по умолчанию
    assert log.message == "Тестовое сообщение"
    assert isinstance(log.created_at, datetime)


def test_log_with_custom_level():
    """TC-LOG-002: Создание лога с указанием уровня"""
    log = Log(
        task_id=1,
        level="ERROR",
        message="Ошибка!"
    )
    
    assert log.level == "ERROR"
    assert log.message == "Ошибка!"


def test_task_logs_relationship(session, test_task):
    """TC-LOG-003: Проверка связи логов с задачей"""
    from src.job_radar.models.log import Log
    
    # Создаем несколько логов для задачи
    log1 = Log(task_id=test_task.id, message="Первый лог")
    log2 = Log(task_id=test_task.id, message="Второй лог")
    session.add_all([log1, log2])
    session.commit()
    
    # Обновляем задачу, чтобы загрузить логи
    session.refresh(test_task)
    
    # Проверяем, что у задачи есть оба лога
    assert len(test_task.logs) == 2
    messages = [log.message for log in test_task.logs]
    assert "Первый лог" in messages
    assert "Второй лог" in messages