"""
Модуль 2 — Unit-тесты чистых утилитарных функций crawler.py
Тестируются без Playwright: _parse_salary, _parse_ru_date, JobCrawler init
"""

import inspect
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call

from src.job_radar.services.crawler import _parse_salary, _parse_ru_date, JobCrawler


# ─────────────────────────────────────────────────────────────
# _parse_salary
# ─────────────────────────────────────────────────────────────

class TestParseSalary:
    """Тесты парсинга строки зарплаты в числа salary_from / salary_to."""

    def test_none_input_returns_none_pair(self):
        assert _parse_salary(None) == (None, None)

    def test_empty_string_returns_none_pair(self):
        assert _parse_salary("") == (None, None)

    def test_from_only(self):
        salary_from, salary_to = _parse_salary("от 100000 руб.")
        assert salary_from == 100000
        assert salary_to is None

    def test_to_only(self):
        salary_from, salary_to = _parse_salary("до 200000 руб.")
        assert salary_from is None
        assert salary_to == 200000

    def test_from_and_to(self):
        salary_from, salary_to = _parse_salary("от 80000 до 120000 руб.")
        assert salary_from == 80000
        assert salary_to == 120000

    def test_single_number_no_keywords(self):

        salary_from, salary_to = _parse_salary("150000 руб.")
        assert salary_from == 150000
        assert salary_to is None  # баг исправлен

    @pytest.mark.xfail(reason="BUG #6: \\u202f (NARROW NO-BREAK SPACE) не удаляется в _parse_salary, "
                               "60\\u202f000 парсится как два числа [60, 0], возвращается 60 вместо 60000. "
                               "Исправление: добавить .replace('\\u202f', '') в начало функции.")
    def test_non_breaking_space_stripped(self):
        """Неразрывные пробелы (\\u202f) должны корректно убираться."""
        salary_from, salary_to = _parse_salary("от\u202f60\u202f000")
        assert salary_from == 60000

    def test_non_breaking_space_current_behavior(self):
        """
        BUG #6 подтверждён: \\u202f не обрабатывается — '60\\u202f000' парсится как 60.
        Актуальное поведение зафиксировано здесь, пока баг не исправлен.
        """
        salary_from, salary_to = _parse_salary("от\u202f60\u202f000")
        # \u202f не убирается, findall находит ["60", "000"] -> [60, 0]
        # "от" есть -> return numbers[0], None -> (60, None)
        assert salary_from == 60

    def test_only_text_no_numbers(self):
        assert _parse_salary("договорная") == (None, None)

    def test_from_greater_than_to_not_swapped(self):
        """Функция не переставляет числа — возвращает как есть."""
        salary_from, salary_to = _parse_salary("от 200000 до 100000")
        assert salary_from == 200000
        assert salary_to == 100000


# ─────────────────────────────────────────────────────────────
# _parse_ru_date
# ─────────────────────────────────────────────────────────────

class TestParseRuDate:
    """Тесты парсинга русскоязычных дат (формат «15 января»)."""

    def test_none_returns_none(self):
        assert _parse_ru_date(None) is None

    def test_empty_returns_none(self):
        assert _parse_ru_date("") is None

    def test_valid_date_january(self):
        result = _parse_ru_date("15 января")
        assert isinstance(result, datetime)
        assert result.day == 15
        assert result.month == 1

    def test_valid_date_december(self):
        result = _parse_ru_date("31 декабря")
        assert result.day == 31
        assert result.month == 12

    def test_valid_date_may(self):
        result = _parse_ru_date("9 мая")
        assert result.month == 5
        assert result.day == 9

    def test_invalid_format_returns_none(self):
        assert _parse_ru_date("2024-01-15") is None

    def test_unknown_month_returns_none(self):
        assert _parse_ru_date("15 julya") is None

    def test_invalid_day_returns_none(self):
        """День 32 — невалидная дата."""
        assert _parse_ru_date("32 января") is None

    def test_date_not_in_future(self):
        """
        BUG #4 (ИСПРАВЛЕН): дата не должна быть в будущем.
        Если разобранная дата > сегодня, год корректируется на предыдущий.
        """
        result = _parse_ru_date("1 января")
        assert result is not None
        now = datetime.now()
        assert result <= now, "Дата оказалась в будущем — год не скорректирован"

    def test_extra_whitespace_handled(self):
        result = _parse_ru_date("  10 марта  ")
        assert result is not None
        assert result.day == 10
        assert result.month == 3


# ─────────────────────────────────────────────────────────────
# JobCrawler инициализация
# ─────────────────────────────────────────────────────────────

class TestJobCrawlerInit:
    def test_default_headless_true(self):
        crawler = JobCrawler()
        assert crawler.headless is True

    def test_custom_headless_false(self):
        crawler = JobCrawler(headless=False)
        assert crawler.headless is False

    def test_default_log_is_callable(self):
        crawler = JobCrawler()
        assert callable(crawler._log)

    def test_custom_log_stored(self):
        custom_log = MagicMock()
        crawler = JobCrawler(log=custom_log)
        crawler._log("test message")
        custom_log.assert_called_once_with("test message")


# ─────────────────────────────────────────────────────────────
# BUG #1: Изменяемый аргумент по умолчанию (mutable default)
# ─────────────────────────────────────────────────────────────

class TestMutableDefaultArgBug:
    """
    BUG #1: В _crawl_hh, _crawl_superjob, _crawl_habr параметр
    known_urls имеет mutable default argument `set()`.
    """

    def _check_mutable_default(self, method_name):
        sig = inspect.signature(getattr(JobCrawler, method_name))
        param = sig.parameters.get("known_urls")
        assert param is not None, f"Параметр known_urls должен существовать в {method_name}"
        default_val = param.default
        if isinstance(default_val, set):
            pytest.xfail(
                f"BUG #1 подтверждён в {method_name}: known_urls имеет mutable default `set()`. "
                "Исправить на `None` с проверкой внутри метода."
            )

    def test_crawl_hh_mutable_default(self):
        self._check_mutable_default("_crawl_hh")

    def test_crawl_superjob_mutable_default(self):
        self._check_mutable_default("_crawl_superjob")

    def test_crawl_habr_mutable_default(self):
        self._check_mutable_default("_crawl_habr")


class TestJobCrawlerCrawlRouting:
    def test_unknown_source_raises_value_error(self):
        """crawl() с неизвестным источником должен бросить ValueError."""
        # Мокируем контекстный менеджер playwright на уровне пакета playwright
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_pw_instance = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser

        mock_pw_cm = MagicMock()
        mock_pw_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
        mock_pw_cm.__exit__ = MagicMock(return_value=False)

        with patch("playwright.sync_api.sync_playwright", return_value=mock_pw_cm):
            crawler = JobCrawler()
            with pytest.raises(ValueError, match="не реализован"):
                crawler.crawl("python", "unknown_source_xyz")