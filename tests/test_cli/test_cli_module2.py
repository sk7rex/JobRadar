"""
Модуль 2 — Unit-тесты новых CLI-команд (app.py)
Тестируются: add, run (mock), task-vacancies, vacancy, stats
Используется typer.testing.CliRunner
"""

import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from sqlmodel import SQLModel, create_engine, Session

from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.vacancy import Vacancy
from src.job_radar.cli.app import app


runner = CliRunner()


# ─────────────────────────────────────────────────────────────
# Фикстуры
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session, engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def patched_session(db_session):
    """Патчим get_session, чтобы команды работали с in-memory БД."""
    session, engine = db_session

    class FakeSessionCtx:
        def __enter__(self): return session
        def __exit__(self, *args): session.commit()

    with patch("src.job_radar.cli.app.get_session", return_value=FakeSessionCtx()):
        yield session


@pytest.fixture
def setup_source(patched_session):
    src = Source(name="habr", url="https://career.habr.com", is_active=True)
    patched_session.add(src)
    patched_session.commit()
    patched_session.refresh(src)
    return src, patched_session


@pytest.fixture
def setup_task_and_vacancy(setup_source):
    src, session = setup_source
    task = SearchTask(keyword="python", source_id=src.id, status=TaskStatus.COMPLETED)
    session.add(task); session.commit(); session.refresh(task)

    vacancy = Vacancy(
        task_id=task.id,
        title="Senior Python Dev",
        company="YandexCorp",
        city="Москва",
        salary_from=150000,
        salary_to=250000,
        url="https://habr.com/v/123",
        description="Ищем опытного разработчика"
    )
    session.add(vacancy); session.commit(); session.refresh(vacancy)
    return task, vacancy, session


# ─────────────────────────────────────────────────────────────
# Команда: add (typer direct)
# ─────────────────────────────────────────────────────────────

class TestAddCommand:

    def test_add_task_success(self, setup_source):
        src, session = setup_source
        result = runner.invoke(app, ["add", "python", "habr"])
        assert result.exit_code == 0
        assert "Задача создана" in result.output or "OK" in result.output

    def test_add_task_nonexistent_source(self, patched_session):
        result = runner.invoke(app, ["add", "python", "nonexistent"])
        assert result.exit_code == 0
        assert "Ошибка" in result.output or "не найден" in result.output

    def test_add_task_inactive_source(self, patched_session):
        src = Source(name="hh", url="https://hh.ru", is_active=False)
        patched_session.add(src); patched_session.commit()
        result = runner.invoke(app, ["add", "python", "hh"])
        assert result.exit_code == 0
        assert "Ошибка" in result.output or "отключен" in result.output

    def test_add_task_with_city(self, setup_source):
        result = runner.invoke(app, ["add", "python", "habr", "Москва"])
        assert result.exit_code == 0

    def test_add_duplicate_task_rejected(self, setup_source):
        runner.invoke(app, ["add", "python", "habr"])
        result = runner.invoke(app, ["add", "python", "habr"])
        assert result.exit_code == 0
        assert "уже в работе" in result.output or "Ошибка" in result.output


# ─────────────────────────────────────────────────────────────
# Команда: vacancy
# ─────────────────────────────────────────────────────────────

class TestVacancyCommand:

    def test_show_existing_vacancy(self, setup_task_and_vacancy):
        task, vacancy, session = setup_task_and_vacancy
        result = runner.invoke(app, ["vacancy", str(vacancy.id)])
        assert result.exit_code == 0
        assert "Senior Python Dev" in result.output
        assert "YandexCorp" in result.output

    def test_show_nonexistent_vacancy(self, patched_session):
        result = runner.invoke(app, ["vacancy", "99999"])
        assert result.exit_code == 0
        assert "не найдена" in result.output

    def test_vacancy_shows_salary(self, setup_task_and_vacancy):
        task, vacancy, session = setup_task_and_vacancy
        result = runner.invoke(app, ["vacancy", str(vacancy.id)])
        assert "150000" in result.output or "от" in result.output


# ─────────────────────────────────────────────────────────────
# Команда: task-vacancies
# ─────────────────────────────────────────────────────────────

class TestTaskVacanciesCommand:

    def test_list_vacancies_for_task(self, setup_task_and_vacancy):
        task, vacancy, session = setup_task_and_vacancy
        result = runner.invoke(app, ["task-vacancies", str(task.id)])

        assert result.exit_code == 0
        assert "Senior" in result.output and "Python Dev" in result.output

    def test_empty_task_shows_message(self, setup_source):
        src, session = setup_source
        task = SearchTask(keyword="go", source_id=src.id, status=TaskStatus.NEW)
        session.add(task); session.commit(); session.refresh(task)
        result = runner.invoke(app, ["task-vacancies", str(task.id)])
        assert result.exit_code == 0
        assert "нет" in result.output.lower()

    def test_nonexistent_task_shows_message(self, patched_session):
        result = runner.invoke(app, ["task-vacancies", "99999"])
        assert result.exit_code == 0
        assert "не найдена" in result.output


# ─────────────────────────────────────────────────────────────
# Команда: stats
# ─────────────────────────────────────────────────────────────

class TestStatsCommand:

    def test_stats_for_task_with_vacancies(self, setup_task_and_vacancy):
        task, vacancy, session = setup_task_and_vacancy
        result = runner.invoke(app, ["stats", str(task.id)])
        assert result.exit_code == 0
        assert str(task.id) in result.output

    def test_stats_for_nonexistent_task(self, patched_session):
        result = runner.invoke(app, ["stats", "99999"])
        assert result.exit_code == 0
        assert "не найдена" in result.output

    def test_stats_for_task_without_vacancies(self, setup_source):
        src, session = setup_source
        task = SearchTask(keyword="ruby", source_id=src.id, status=TaskStatus.COMPLETED)
        session.add(task); session.commit(); session.refresh(task)
        result = runner.invoke(app, ["stats", str(task.id)])
        assert result.exit_code == 0
        assert "нет" in result.output.lower() or str(task.id) in result.output


# ─────────────────────────────────────────────────────────────
# Команда: vacancies (список)
# ─────────────────────────────────────────────────────────────

class TestVacanciesListCommand:

    def test_no_vacancies_shows_message(self, patched_session):
        result = runner.invoke(app, ["vacancies"])
        assert result.exit_code == 0
        assert "нет" in result.output.lower()

    def test_vacancies_shown_when_present(self, setup_task_and_vacancy):
        result = runner.invoke(app, ["vacancies"])
        assert result.exit_code == 0
        assert "Senior Python Dev" in result.output

    def test_vacancies_with_limit(self, setup_source):
        src, session = setup_source
        task = SearchTask(keyword="ml", source_id=src.id, status=TaskStatus.COMPLETED)
        session.add(task); session.commit(); session.refresh(task)
        for i in range(5):
            v = Vacancy(task_id=task.id, title=f"Dev {i}",
                        url=f"https://habr.com/v/{i}")
            session.add(v)
        session.commit()
        result = runner.invoke(app, ["vacancies", "--limit", "3"])
        assert result.exit_code == 0


# ─────────────────────────────────────────────────────────────
# Команда: run (краулер — мокируем)
# ─────────────────────────────────────────────────────────────

class TestRunCommand:

    def test_run_no_new_tasks_shows_message(self, patched_session):
        result = runner.invoke(app, ["run"])
        assert result.exit_code == 0
        assert "нет задач" in result.output.lower() or "NEW" in result.output

    @patch("src.job_radar.services.crawler.JobCrawler")
    def test_run_specific_nonexistent_task(self, mock_crawler_cls, patched_session):
        result = runner.invoke(app, ["run", "99999"])
        assert result.exit_code == 0
        assert "не найдена" in result.output

    @patch("src.job_radar.services.crawler.JobCrawler")
    def test_run_calls_crawler_for_new_task(self, mock_crawler_cls, setup_source):
        src, session = setup_source
        task = SearchTask(keyword="python", source_id=src.id, status=TaskStatus.NEW)
        session.add(task); session.commit(); session.refresh(task)

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = []
        mock_crawler_cls.return_value = mock_crawler

        result = runner.invoke(app, ["run", str(task.id)])
        assert result.exit_code == 0
        mock_crawler.crawl.assert_called_once()

    @patch("src.job_radar.services.crawler.JobCrawler")
    def test_run_saves_returned_vacancies(self, mock_crawler_cls, setup_source):
        src, session = setup_source
        task = SearchTask(keyword="python", source_id=src.id, status=TaskStatus.NEW)
        session.add(task); session.commit(); session.refresh(task)

        fake_vacancy = {
            "url": "https://habr.com/v/42",
            "title": "Crawler Vacancy",
            "company": "TestCo",
            "city": "СПб",
            "salary_from": None,
            "salary_to": None,
            "description": None,
            "published_at": None,
        }

        mock_crawler = MagicMock()
        mock_crawler.crawl.return_value = [fake_vacancy]
        mock_crawler_cls.return_value = mock_crawler

        result = runner.invoke(app, ["run", str(task.id)])
        assert result.exit_code == 0
        assert "Завершено" in result.output or "сохранено" in result.output.lower()


# ─────────────────────────────────────────────────────────────
# Команда: count
# ─────────────────────────────────────────────────────────────

class TestCountCommand:

    def test_count_zero(self, patched_session):
        result = runner.invoke(app, ["count"])
        assert result.exit_code == 0
        assert "0" in result.output

    def test_count_after_add(self, setup_task_and_vacancy):
        result = runner.invoke(app, ["count"])
        assert result.exit_code == 0
        assert "1" in result.output


# ─────────────────────────────────────────────────────────────
# Команда: description
# ─────────────────────────────────────────────────────────────

class TestDescriptionCommand:

    def test_description_shown(self, setup_task_and_vacancy):
        task, vacancy, session = setup_task_and_vacancy
        result = runner.invoke(app, ["description", str(vacancy.id)])
        assert result.exit_code == 0
        assert "опытного" in result.output

    def test_description_not_found(self, patched_session):
        result = runner.invoke(app, ["description", "99999"])
        assert result.exit_code == 0
        assert "не найдена" in result.output

    def test_description_empty(self, setup_source):
        src, session = setup_source
        task = SearchTask(keyword="qa", source_id=src.id, status=TaskStatus.COMPLETED)
        session.add(task); session.commit(); session.refresh(task)
        v = Vacancy(task_id=task.id, title="QA Engineer",
                    url="https://habr.com/v/qa", description=None)
        session.add(v); session.commit(); session.refresh(v)
        result = runner.invoke(app, ["description", str(v.id)])
        assert result.exit_code == 0
        assert "нет описания" in result.output
