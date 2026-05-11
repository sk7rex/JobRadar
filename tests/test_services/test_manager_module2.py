"""
Модуль 2 — Unit-тесты новых методов TaskManager
Покрываются: save_parsed_vacancy, get_pending_tasks,
             get_vacancy, list_vacancies_by_task, get_task_stats,
             count_vacancies, list_vacancies, list_logs
"""

import pytest
from datetime import datetime
from sqlmodel import SQLModel, create_engine, Session

# Импорты моделей
from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.vacancy import Vacancy
from src.job_radar.models.log import Log
from src.job_radar.services.manager import TaskManager


# ─────────────────────────────────────────────────────────────
# Фикстуры
# ─────────────────────────────────────────────────────────────

@pytest.fixture(name="session")
def session_fixture():
    """In-memory SQLite сессия для изолированных тестов."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def active_source(session):
    src = Source(name="habr", url="https://career.habr.com", is_active=True)
    session.add(src)
    session.commit()
    session.refresh(src)
    return src


@pytest.fixture
def inactive_source(session):
    src = Source(name="geekjob", url="https://geekjob.ru", is_active=False)
    session.add(src)
    session.commit()
    session.refresh(src)
    return src


@pytest.fixture
def new_task(session, active_source):
    task = SearchTask(
        keyword="python",
        source_id=active_source.id,
        status=TaskStatus.NEW
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@pytest.fixture
def completed_task(session, active_source):
    task = SearchTask(
        keyword="java",
        source_id=active_source.id,
        status=TaskStatus.COMPLETED
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@pytest.fixture
def manager(session):
    return TaskManager(session)


def make_vacancy_data(url="https://habr.com/v/1", **kwargs):
    data = {
        "url": url,
        "title": "Python Developer",
        "company": "Acme Corp",
        "city": "Москва",
        "salary_from": 100000,
        "salary_to": 200000,
        "description": "Some description",
        "published_at": datetime(2025, 3, 1),
    }
    data.update(kwargs)
    return data


# ─────────────────────────────────────────────────────────────
# save_parsed_vacancy
# ─────────────────────────────────────────────────────────────

class TestSaveParsedVacancy:

    def test_save_creates_vacancy(self, manager, session, new_task):
        data = make_vacancy_data()
        v = manager.save_parsed_vacancy(new_task.id, data)
        assert v.id is not None
        assert v.title == "Python Developer"
        assert v.url == "https://habr.com/v/1"

    def test_save_increments_items_found(self, manager, session, new_task):
        assert new_task.items_found == 0
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        session.refresh(new_task)
        assert new_task.items_found == 1

    def test_save_multiple_increments_items_found(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        session.refresh(new_task)
        assert new_task.items_found == 2

    def test_save_duplicate_url_raises(self, manager, new_task):
        data = make_vacancy_data()
        manager.save_parsed_vacancy(new_task.id, data)
        with pytest.raises(ValueError, match="уже в БД"):
            manager.save_parsed_vacancy(new_task.id, data)

    def test_save_creates_log(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data())
        logs = session.exec(
            __import__("sqlmodel").select(Log).where(Log.task_id == new_task.id)
        ).all()
        assert any("Saved vacancy" in log.message for log in logs)

    def test_save_with_minimal_data(self, manager, session, new_task):
        """Вакансия без необязательных полей должна сохраняться."""
        data = {"url": "https://habr.com/v/min", "title": None}
        v = manager.save_parsed_vacancy(new_task.id, data)
        assert v.title == "No Title"
        assert v.company is None
        assert v.salary_from is None

    def test_save_does_not_update_updated_at(self, manager, session, new_task):
        original_updated_at = new_task.updated_at
        import time; time.sleep(0.05)
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data())
        session.refresh(new_task)

        assert new_task.updated_at > original_updated_at


# ─────────────────────────────────────────────────────────────
# get_pending_tasks
# ─────────────────────────────────────────────────────────────

class TestGetPendingTasks:

    def test_returns_only_new_tasks(self, manager, session, active_source):
        t1 = SearchTask(keyword="go", source_id=active_source.id, status=TaskStatus.NEW)
        t2 = SearchTask(keyword="rust", source_id=active_source.id, status=TaskStatus.COMPLETED)
        t3 = SearchTask(keyword="c++", source_id=active_source.id, status=TaskStatus.IN_PROGRESS)
        session.add_all([t1, t2, t3])
        session.commit()

        pending = manager.get_pending_tasks()
        statuses = {t.status for t in pending}
        assert statuses == {TaskStatus.NEW}

    def test_returns_empty_when_no_new_tasks(self, manager, session, active_source):
        t = SearchTask(keyword="kotlin", source_id=active_source.id, status=TaskStatus.COMPLETED)
        session.add(t)
        session.commit()
        assert manager.get_pending_tasks() == []

    def test_ordered_by_created_at_asc(self, manager, session, active_source):
        import time
        t1 = SearchTask(keyword="first", source_id=active_source.id, status=TaskStatus.NEW)
        session.add(t1); session.commit()
        time.sleep(0.05)
        t2 = SearchTask(keyword="second", source_id=active_source.id, status=TaskStatus.NEW)
        session.add(t2); session.commit()

        pending = manager.get_pending_tasks()
        assert pending[0].keyword == "first"
        assert pending[1].keyword == "second"

    def test_source_relation_loaded(self, manager, session, active_source):
        """Отношение source_relation должно быть загружено без lazy-loading."""
        t = SearchTask(keyword="scala", source_id=active_source.id, status=TaskStatus.NEW)
        session.add(t); session.commit()
        pending = manager.get_pending_tasks()
        assert pending[0].source_relation is not None
        assert pending[0].source_relation.name == "habr"


# ─────────────────────────────────────────────────────────────
# get_vacancy
# ─────────────────────────────────────────────────────────────

class TestGetVacancy:

    def test_returns_vacancy_by_id(self, manager, session, new_task):
        v = manager.save_parsed_vacancy(new_task.id, make_vacancy_data())
        result = manager.get_vacancy(v.id)
        assert result is not None
        assert result.id == v.id
        assert result.title == "Python Developer"

    def test_returns_none_for_missing_id(self, manager):
        assert manager.get_vacancy(99999) is None


# ─────────────────────────────────────────────────────────────
# list_vacancies_by_task
# ─────────────────────────────────────────────────────────────

class TestListVacanciesByTask:

    def test_returns_vacancies_for_task(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        result = manager.list_vacancies_by_task(new_task.id)
        assert len(result) == 2

    def test_returns_empty_for_task_without_vacancies(self, manager, new_task):
        result = manager.list_vacancies_by_task(new_task.id)
        assert result == []

    def test_does_not_return_other_task_vacancies(self, manager, session, active_source, new_task):
        other_task = SearchTask(keyword="devops", source_id=active_source.id, status=TaskStatus.NEW)
        session.add(other_task); session.commit()

        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(other_task.id, make_vacancy_data(url="https://habr.com/v/2"))

        result = manager.list_vacancies_by_task(new_task.id)
        assert len(result) == 1
        assert result[0].url == "https://habr.com/v/1"

    def test_ordered_by_id_asc(self, manager, session, new_task):
        v1 = manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        v2 = manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        result = manager.list_vacancies_by_task(new_task.id)
        assert result[0].id < result[1].id


# ─────────────────────────────────────────────────────────────
# get_task_stats
# ─────────────────────────────────────────────────────────────

class TestGetTaskStats:

    def test_returns_none_for_missing_task(self, manager):
        assert manager.get_task_stats(99999) is None

    def test_returns_zero_stats_when_no_vacancies(self, manager, new_task):
        stats = manager.get_task_stats(new_task.id)
        assert stats is not None
        assert stats["total"] == 0

    def test_total_count(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        stats = manager.get_task_stats(new_task.id)
        assert stats["total"] == 2

    def test_with_salary_count(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1",
                                                                    salary_from=100000, salary_to=None))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2",
                                                                    salary_from=None, salary_to=None))
        stats = manager.get_task_stats(new_task.id)
        assert stats["with_salary"] == 1

    def test_salary_min_max_median(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1",
                                                                    salary_from=50000))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2",
                                                                    salary_from=100000))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/3",
                                                                    salary_from=150000))
        stats = manager.get_task_stats(new_task.id)
        assert stats["salary_min"] == 50000
        assert stats["salary_max"] == 150000
        assert stats["salary_median"] == 100000

    def test_top_companies_present(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1", company="Yandex"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2", company="Yandex"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/3", company="VK"))
        stats = manager.get_task_stats(new_task.id)
        companies = dict(stats["top_companies"])
        assert companies.get("Yandex") == 2
        assert companies.get("VK") == 1

    def test_with_city_count(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1", city="Москва"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2", city=None))
        stats = manager.get_task_stats(new_task.id)
        assert stats["with_city"] == 1

    def test_with_description_count(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1",
                                                                    description="Big description"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2",
                                                                    description=None))
        stats = manager.get_task_stats(new_task.id)
        assert stats["with_description"] == 1

    def test_date_min_max(self, manager, session, new_task):
        d1 = datetime(2025, 1, 1)
        d2 = datetime(2025, 6, 1)
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1", published_at=d1))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2", published_at=d2))
        stats = manager.get_task_stats(new_task.id)
        assert stats["date_min"] == d1
        assert stats["date_max"] == d2

    def test_salary_stats_none_when_no_salary(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1",
                                                                    salary_from=None, salary_to=None))
        stats = manager.get_task_stats(new_task.id)
        assert stats["salary_min"] is None
        assert stats["salary_max"] is None
        assert stats["salary_median"] is None


# ─────────────────────────────────────────────────────────────
# count_vacancies
# ─────────────────────────────────────────────────────────────

class TestCountVacancies:

    def test_returns_zero_initially(self, manager):
        assert manager.count_vacancies() == 0

    def test_returns_correct_count(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        assert manager.count_vacancies() == 2


# ─────────────────────────────────────────────────────────────
# list_vacancies (с лимитом)
# ─────────────────────────────────────────────────────────────

class TestListVacancies:

    def test_returns_empty_when_no_vacancies(self, manager):
        assert manager.list_vacancies() == []

    def test_respects_limit(self, manager, session, new_task):
        for i in range(15):
            manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url=f"https://habr.com/v/{i}"))
        result = manager.list_vacancies(limit=5)
        assert len(result) == 5

    def test_ordered_by_id_desc(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        result = manager.list_vacancies(limit=10)
        assert result[0].id > result[1].id


# ─────────────────────────────────────────────────────────────
# list_logs
# ─────────────────────────────────────────────────────────────

class TestListLogs:

    def test_returns_empty_when_no_logs(self, manager, session):
        assert manager.list_logs() == []

    def test_returns_logs_in_desc_order(self, manager, session, new_task):
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/1"))
        manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url="https://habr.com/v/2"))
        logs = manager.list_logs(limit=10)
        if len(logs) >= 2:
            assert logs[0].created_at >= logs[1].created_at

    def test_respects_limit(self, manager, session, new_task):
        for i in range(10):
            manager.save_parsed_vacancy(new_task.id, make_vacancy_data(url=f"https://habr.com/v/{i}"))
        logs = manager.list_logs(limit=3)
        assert len(logs) <= 3
