"""
Mock-тесты для краулера (без реального интернет-соединения).
"""
import pytest
from unittest.mock import MagicMock, patch, call
from src.job_radar.services.crawler import JobCrawler, _parse_salary


# ── Unit-тесты утилиты парсинга зарплаты ──────────────────────────────────────

def test_parse_salary_from_to():
    assert _parse_salary("от 100 000 до 200 000 руб") == (100000, 200000)


def test_parse_salary_from_only():
    assert _parse_salary("от 80 000 руб") == (80000, None)


def test_parse_salary_to_only():
    assert _parse_salary("до 120 000 руб") == (None, 120000)


def test_parse_salary_fixed():
    assert _parse_salary("150 000 руб") == (150000, None)


def test_parse_salary_none():
    assert _parse_salary(None) == (None, None)


def test_parse_salary_empty():
    assert _parse_salary("") == (None, None)


def test_parse_salary_no_numbers():
    assert _parse_salary("договорная") == (None, None)


# ── Mock-тесты _crawl_hh (извлечение из карточек поиска) ─────────────────────

FAKE_CARDS = [
    {
        "url": "https://hh.ru/vacancy/100",
        "title": "Senior Python Developer",
        "company": "ООО Тест",
        "salary_raw": "от 200 000 до 300 000 руб",
        "city": "Москва",
        "description": "Python, Django, PostgreSQL",
    },
    {
        "url": "https://hh.ru/vacancy/101",
        "title": "Junior Python Developer",
        "company": "ИП Иванов",
        "salary_raw": None,
        "city": "Санкт-Петербург",
        "description": None,
    },
]


def _make_hh_page_mock(cards=FAKE_CARDS, has_next=False):
    page = MagicMock()
    page.goto.return_value = None
    page.wait_for_selector.return_value = None
    page.evaluate.return_value = cards
    page.query_selector.return_value = MagicMock() if has_next else None
    return page


def test_crawl_hh_returns_all_cards():
    crawler = JobCrawler()
    page = _make_hh_page_mock()
    result = crawler._crawl_hh(page, "python", None)
    assert len(result) == 2


def test_crawl_hh_card_fields():
    crawler = JobCrawler()
    page = _make_hh_page_mock()
    result = crawler._crawl_hh(page, "python", None)
    first = result[0]
    assert first["url"] == "https://hh.ru/vacancy/100"
    assert first["title"] == "Senior Python Developer"
    assert first["company"] == "ООО Тест"
    assert first["city"] == "Москва"
    assert first["salary_from"] == 200000
    assert first["salary_to"] == 300000
    assert first["description"] == "Python, Django, PostgreSQL"


def test_crawl_hh_card_missing_salary():
    crawler = JobCrawler()
    page = _make_hh_page_mock()
    result = crawler._crawl_hh(page, "python", None)
    second = result[1]
    assert second["salary_from"] is None
    assert second["salary_to"] is None


def test_crawl_hh_card_missing_description():
    crawler = JobCrawler()
    page = _make_hh_page_mock()
    result = crawler._crawl_hh(page, "python", None)
    assert result[1]["description"] is None


def test_crawl_hh_published_at_is_none():
    """Дата публикации недоступна в карточках поиска."""
    crawler = JobCrawler()
    page = _make_hh_page_mock()
    result = crawler._crawl_hh(page, "python", None)
    assert all(v["published_at"] is None for v in result)


def test_crawl_hh_stops_when_no_cards():
    crawler = JobCrawler()
    page = _make_hh_page_mock(cards=[])
    result = crawler._crawl_hh(page, "python", None)
    assert result == []


def test_crawl_hh_stops_when_no_next_page():
    """Без кнопки «следующая страница» краулер не переходит на вторую страницу поиска."""
    crawler = JobCrawler()
    page = _make_hh_page_mock(cards=FAKE_CARDS, has_next=False)
    with patch.object(crawler, "_delay"):
        result = crawler._crawl_hh(page, "python", None)
    # 1 переход на страницу поиска + по одному переходу на страницу каждой вакансии
    assert page.goto.call_count == 1 + len(FAKE_CARDS)


# ── Тест неизвестного источника ───────────────────────────────────────────────

def test_crawl_unknown_source_raises():
    crawler = JobCrawler()
    with patch("playwright.sync_api.sync_playwright") as mock_pw:
        mock_pw.return_value.__enter__.return_value = MagicMock()
        mock_pw.return_value.__exit__.return_value = False
        with pytest.raises(ValueError, match="не реализован"):
            crawler.crawl("python", "linkedin")


# ── Тесты TaskManager.save_parsed_vacancy ────────────────────────────────────

def test_save_parsed_vacancy(manager, test_task):
    """TC-MANAGER-NEW-001: Сохранение вакансии через save_parsed_vacancy."""
    data = {
        "url": "https://hh.ru/vacancy/132464534",
        "title": "Python Developer",
        "company": "Test Corp",
        "city": "Москва",
        "description": "Test description",
        "salary_from": 100000,
        "salary_to": 150000,
        "published_at": None,
    }
    vacancy = manager.save_parsed_vacancy(test_task.id, data)
    assert vacancy.id is not None
    assert vacancy.title == "Python Developer"
    assert vacancy.salary_from == 100000


def test_save_parsed_vacancy_increments_items_found(manager, session, test_task):
    """TC-MANAGER-NEW-002: items_found увеличивается при сохранении вакансии."""
    from src.job_radar.models.task import SearchTask

    before = session.get(SearchTask, test_task.id).items_found
    manager.save_parsed_vacancy(test_task.id, {
        "url": "https://hh.ru/vacancy/132464534",
        "title": "QA Engineer",
    })
    after = session.get(SearchTask, test_task.id).items_found
    assert after == before + 1


def test_save_parsed_vacancy_duplicate_raises(manager, test_task):
    """TC-MANAGER-NEW-003: Дублирующий URL должен вызвать ValueError."""
    data = {"url": "https://hh.ru/vacancy/132464534", "title": "Dev"}
    manager.save_parsed_vacancy(test_task.id, data)
    with pytest.raises(ValueError) as exc_info:
        manager.save_parsed_vacancy(test_task.id, data)
    assert "уже в БД" in str(exc_info.value)


def test_get_pending_tasks(manager, session, test_source):
    """TC-MANAGER-NEW-004: get_pending_tasks возвращает только NEW задачи."""
    from src.job_radar.models.task import SearchTask, TaskStatus

    task1 = SearchTask(source_id=test_source.id, keyword="golang", status=TaskStatus.NEW)
    task2 = SearchTask(source_id=test_source.id, keyword="rust", status=TaskStatus.COMPLETED)
    session.add_all([task1, task2])
    session.commit()

    pending = manager.get_pending_tasks()
    keywords = [t.keyword for t in pending]
    assert "golang" in keywords
    assert "rust" not in keywords
