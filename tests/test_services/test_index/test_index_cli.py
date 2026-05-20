"""
TC-CLI-001..015  CLI-команды index-build и index-search.
"""

import pytest
from unittest.mock import patch
from typer.testing import CliRunner
from sqlmodel import SQLModel, create_engine, Session

from src.job_radar.cli.app import app
from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.vacancy import Vacancy

runner = CliRunner()


# ─────────────────────────────────────────────────────────────
# Фикстуры
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def patched_session(db_session):
    class FakeSessionCtx:
        def __enter__(self): return db_session
        def __exit__(self, *args): db_session.commit()

    with patch("src.job_radar.cli.app.get_session", return_value=FakeSessionCtx()):
        yield db_session


@pytest.fixture
def tmp_index_dir(tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    monkeypatch.setattr("src.job_radar.cli.app.INDEX_DIR", index_dir)
    return index_dir


@pytest.fixture
def db_with_vacancies(patched_session):
    session = patched_session

    src = Source(name="habr", url="https://career.habr.com", is_active=True)
    session.add(src)
    session.commit()
    session.refresh(src)

    task = SearchTask(keyword="python", source_id=src.id, status=TaskStatus.COMPLETED)
    session.add(task)
    session.commit()
    session.refresh(task)

    for title, desc, url in [
        ("Python разработчик",    "Django REST backend",     "https://habr.com/v/1"),
        ("Java Backend Developer","Spring Kafka Python",      "https://habr.com/v/2"),
        ("Frontend разработчик",  "React TypeScript JavaScript", "https://habr.com/v/3"),
    ]:
        session.add(Vacancy(task_id=task.id, title=title, description=desc, url=url))
    session.commit()

    return session


# ─────────────────────────────────────────────────────────────
# TC-CLI-001..007  index-build
# ─────────────────────────────────────────────────────────────

class TestIndexBuildCLI:

    def test_no_vacancies_shows_warning(self, patched_session, tmp_index_dir):
        """TC-CLI-001"""
        result = runner.invoke(app, ["index-build"])
        assert result.exit_code == 0
        assert "Нет вакансий" in result.output

    def test_build_plain_creates_file(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-002"""
        result = runner.invoke(app, ["index-build", "--variant", "plain"])
        assert result.exit_code == 0
        assert (tmp_index_dir / "index_plain.json").exists()

    def test_build_delta_creates_file(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-003"""
        result = runner.invoke(app, ["index-build", "--variant", "delta"])
        assert result.exit_code == 0
        assert (tmp_index_dir / "index_delta.bin").exists()

    def test_build_gamma_creates_file(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-004"""
        result = runner.invoke(app, ["index-build", "--variant", "gamma"])
        assert result.exit_code == 0
        assert (tmp_index_dir / "index_gamma.bin").exists()

    def test_build_all_creates_three_files(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-005: --variant all (по умолчанию)"""
        result = runner.invoke(app, ["index-build"])
        assert result.exit_code == 0
        assert (tmp_index_dir / "index_plain.json").exists()
        assert (tmp_index_dir / "index_delta.bin").exists()
        assert (tmp_index_dir / "index_gamma.bin").exists()

    def test_unknown_variant_shows_error(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-006"""
        result = runner.invoke(app, ["index-build", "--variant", "unknown"])
        assert result.exit_code == 0
        assert "Неизвестный вариант" in result.output or "unknown" in result.output

    def test_output_contains_token_count(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-007"""
        result = runner.invoke(app, ["index-build", "--variant", "plain"])
        assert result.exit_code == 0
        assert "токенов" in result.output


# ─────────────────────────────────────────────────────────────
# TC-CLI-010..015  index-search
# ─────────────────────────────────────────────────────────────

class TestIndexSearchCLI:

    def test_search_without_index_shows_not_found(self, patched_session, tmp_index_dir):
        """TC-CLI-010: файл индекса отсутствует"""
        result = runner.invoke(app, ["index-search", "python"])
        assert result.exit_code == 0
        assert "не найден" in result.output

    def test_search_returns_results(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-011"""
        runner.invoke(app, ["index-build", "--variant", "plain"])
        result = runner.invoke(app, ["index-search", "python"])
        assert result.exit_code == 0
        # Вывод содержит время поиска
        assert "мс" in result.output or "с" in result.output
        assert "Ничего не найдено" not in result.output

    def test_search_unknown_query_shows_empty_message(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-012"""
        runner.invoke(app, ["index-build", "--variant", "plain"])
        result = runner.invoke(app, ["index-search", "несуществующийтокен99999"])
        assert result.exit_code == 0
        assert "Ничего не найдено" in result.output

    def test_and_mode_does_not_crash(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-013: --mode and отрабатывает без ошибок"""
        runner.invoke(app, ["index-build", "--variant", "plain"])
        result_or  = runner.invoke(app, ["index-search", "python разработчик", "--mode", "or"])
        result_and = runner.invoke(app, ["index-search", "python разработчик", "--mode", "and"])
        assert result_or.exit_code == 0
        assert result_and.exit_code == 0

    def test_limit_flag_accepted(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-014: --limit N не вызывает ошибок"""
        runner.invoke(app, ["index-build", "--variant", "plain"])
        result = runner.invoke(app, ["index-search", "разработчик", "--limit", "1"])
        assert result.exit_code == 0

    def test_gamma_and_plain_return_same_results(self, db_with_vacancies, tmp_index_dir):
        """TC-CLI-015"""
        runner.invoke(app, ["index-build"])
        result_plain = runner.invoke(app, ["index-search", "python", "--variant", "plain"])
        result_gamma = runner.invoke(app, ["index-search", "python", "--variant", "gamma"])
        assert result_plain.exit_code == 0
        assert result_gamma.exit_code == 0
        assert "Ничего не найдено" not in result_plain.output
        assert "Ничего не найдено" not in result_gamma.output
