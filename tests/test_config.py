import pytest
from pathlib import Path
from src.job_radar import config


def test_base_dir():
    """TC-CONF-001: Проверка базового пути"""
    assert isinstance(config.BASE_DIR, Path)
    assert config.BASE_DIR.name == "JobRadar"


def test_allowed_sources():
    """TC-CONF-002: Проверка списка разрешенных источников"""
    expected = {"habr", "hh", "geekjob", "linkedin"}
    assert config.ALLOWED_SOURCES == expected


def test_database_url():
    """Проверка формирования URL БД"""
    assert config.DATABASE_URL.startswith("sqlite:///")
    assert "job_radar.db" in config.DATABASE_URL
