import re
import pytest
from typer.testing import CliRunner
from sqlalchemy import create_engine, delete, select
from src.job_radar.cli.app import app
from src.job_radar.database import init_db, get_session
from src.job_radar.models.task import SearchTask
from src.job_radar.models.source import Source

runner = CliRunner()



# =========================================================
# Source commands (только в интерактиве)
# =========================================================

def test_interactive_add_source():
    # Добавляем через интерактив
    result_add = runner.invoke(app, ["interactive"], input="add source test124 https://linkedin.com\nexit\n")
    assert "Источник добавлен" in result_add.output
    
    # Удаляем через интерактив
    result_del = runner.invoke(app, ["interactive"], input="rm source test124\nexit\n")
    assert "удален" in result_del.output
    
    # Проверяем, что источника действительно нет
    with get_session() as session:
        sources = session.exec(select(Source)).scalars().all()
        assert not any(s.name == "test124" for s in sources)

# =========================================================
# Task commands
# =========================================================

def test_interactive_add_task():
    """Создание и удаление задачи через интерактивный режим."""
    
    result_add = runner.invoke(app, ["interactive"], input="add python backend habr\nexit\n")
    assert "Задача создана" in result_add.output
    
    with get_session() as session:
        task = session.exec(select(SearchTask).where(SearchTask.keyword == "python backend")).scalars().first()
        task_id = task.id
    
    result_del = runner.invoke(app, ["interactive"], input=f"rm task {task_id}\nexit\n")
    assert "удалена" in result_del.output
    
    with get_session() as session:
        deleted_task = session.get(SearchTask, task_id)
        assert deleted_task is None


def test_interactive_add_task_invalid_source():
    """Создание задачи с отсутствующим источником должно падать."""
    result = runner.invoke(app, ["interactive"], input="add python nosource\nexit\n")

    assert any([
        "Ошибка" in result.output,
        "не найден" in result.output
    ])


# =========================================================
# List commands
# =========================================================

def test_interactive_list_tasks():
    """Команда tasks должна показывать созданные задачи."""
    runner.invoke(app, ["interactive"], input="add source habr https://habr.com\nexit\n")
    runner.invoke(app, ["interactive"], input="add python habr\nexit\n")

    result = runner.invoke(app, ["interactive"], input="tasks\nexit\n")
    assert "python" in result.output


def test_interactive_list_sources():
    """Команда sources должна показывать доступные источники."""
    runner.invoke(app, ["interactive"], input="add source mysource https://mysite.com\nexit\n")

    result = runner.invoke(app, ["interactive"], input="sources\nexit\n")
    assert "mysource" in result.output


def test_list_vacancies_empty():
    """Список вакансий должен показывать сообщение о пустоте."""
    result = runner.invoke(app, ["interactive"], input="vacancies\nexit\n")
    assert "Вакансий пока нет" in result.output


# =========================================================
# Interactive mode
# =========================================================

def test_interactive_help():
    """Интерактивный режим должен показывать help."""
    result = runner.invoke(app, ["interactive"], input="help\nexit\n")
    assert result.exit_code == 0
    assert "Доступные команды" in result.output


def test_interactive_unknown_command():
    """Неизвестная команда должна выдавать ошибку."""
    result = runner.invoke(app, ["interactive"], input="someunknowncommand\nexit\n")
    assert "Неизвестная команда" in result.output


def test_interactive_tasks_with_limit():
    """Просмотр задач с лимитом в интерактивном режиме."""
    runner.invoke(app, ["interactive"], input="add source habr https://habr.com\nexit\n")
    runner.invoke(app, ["interactive"], input="add python habr\nadd java habr\nexit\n")
    
    result = runner.invoke(app, ["interactive"], input="tasks 14\nexit\n")
    assert "Задачи (последние 14)" in result.output