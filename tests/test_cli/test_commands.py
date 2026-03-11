import pytest
import subprocess
import sqlite3
import os
import time


def run_cli_command(args, input_text=None):
    """Вспомогательная функция для запуска CLI команд"""
    cmd = ["python", "-m", "src.job_radar.main"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text
    )
    return result


@pytest.fixture
def clean_db():
    """Удаляет БД перед тестом и восстанавливает после"""
    db_path = "job_radar.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    yield
    if os.path.exists(db_path):
        os.remove(db_path)


def test_cli_init_first_time(clean_db):
    """TC-CLI-001: Инициализация БД при первом запуске"""
    result = run_cli_command(["init"])
    
    assert "успешно инициализирована" in result.stdout
    assert os.path.exists("job_radar.db")
    
    # Проверка структуры БД
    conn = sqlite3.connect("job_radar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    assert "searchtask" in tables
    conn.close()


def test_cli_init_second_time(clean_db):
    """Повторная инициализация БД"""
    # Первый запуск
    run_cli_command(["init"])
    
    # Второй запуск
    result = run_cli_command(["init"])
    assert "уже инициализирована" in result.stdout


def test_cli_add_valid_task(clean_db):
    """TC-CLI-002: Добавление задачи с корректными параметрами"""
    # Инициализация БД
    run_cli_command(["init"])
    
    # Добавление задачи
    result = run_cli_command(["add", "python", "habr"])
    
    assert "Задача создана" in result.stdout
    assert "ID:" in result.stdout
    
    # Проверка в БД
    conn = sqlite3.connect("job_radar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT keyword, source FROM searchtask WHERE keyword='python'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "python"
    assert row[1] == "habr"
    conn.close()


def test_cli_add_composite_keyword(clean_db):
    """TC-CLI-003: Добавление задачи с составным ключевым словом"""
    run_cli_command(["init"])
    
    result = run_cli_command(["add", "python developer", "habr"])
    assert "Задача создана" in result.stdout
    
    conn = sqlite3.connect("job_radar.db")
    cursor = conn.cursor()
    cursor.execute("SELECT keyword FROM searchtask")
    row = cursor.fetchone()
    assert row[0] == "python developer"
    conn.close()


def test_cli_add_invalid_source(clean_db):
    """TC-CLI-004: Добавление задачи с недопустимым источником"""
    run_cli_command(["init"])
    
    result = run_cli_command(["add", "python", "invalid"])
    
    assert "Источник 'invalid' недоступен" in result.stderr or "недоступен" in result.stdout


def test_cli_list_tasks(clean_db):
    """TC-CLI-005: Просмотр списка задач"""
    run_cli_command(["init"])
    
    # Добавляем несколько задач
    for keyword in ["python", "java", "javascript"]:
        run_cli_command(["add", keyword, "habr"])
        time.sleep(0.1)  # Для разницы во времени
    
    result = run_cli_command(["list"])
    
    assert "Очередь задач" in result.stdout
    assert "python" in result.stdout
    assert "java" in result.stdout
    assert "javascript" in result.stdout


def test_cli_list_with_limit(clean_db):
    """TC-CLI-006: Просмотр списка с лимитом"""
    run_cli_command(["init"])
    
    # Добавляем 15 задач
    for i in range(15):
        run_cli_command(["add", f"python{i}", "habr"])
    
    result_limit5 = run_cli_command(["list", "5"])
    # Должно быть 5 строк с задачами + заголовок
    assert result_limit5.stdout.count("python") == 5
    
    result_limit20 = run_cli_command(["list", "20"])
    assert result_limit20.stdout.count("python") == 15


def test_cli_help():
    """Проверка помощи"""
    result = run_cli_command(["--help"])
    assert "Usage" in result.stdout
    assert "Commands" in result.stdout
    assert "init" in result.stdout
    assert "add" in result.stdout
    assert "list" in result.stdout
