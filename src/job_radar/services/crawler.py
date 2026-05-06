import random
import re
import time
from datetime import datetime
from typing import Callable, Optional
from urllib.parse import quote_plus

from src.job_radar.config import (
    CARD_RETRIES, FETCH_DESCRIPTIONS,
    HABR_CITY_IDS, HEADLESS, HH_CITY_IDS, HH_DEFAULT_AREA,
    MAX_PAGES, MAX_DELAY, MIN_DELAY, SUPERJOB_CITY_IDS,
)


class JobCrawler:
    def __init__(self, headless: bool = HEADLESS, log: Optional[Callable] = None):
        self.headless = headless
        self._log = log if log is not None else lambda msg: print(msg, flush=True)

    def crawl(
        self,
        keyword: str,
        source: str,
        city: Optional[str] = None,
        known_urls: set[str] | None = None,
    ) -> list[dict]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8"},
            )
            page = context.new_page()
            try:
                if source == "hh":
                    return self._crawl_hh(page, keyword, city, known_urls or set())
                elif source == "superjob":
                    return self._crawl_superjob(page, keyword, city, known_urls or set())
                elif source == "habr":
                    return self._crawl_habr(page, keyword, city, known_urls or set())
                else:
                    raise ValueError(f"Краулер не реализован для источника: {source}")
            finally:
                browser.close()

    # ── hh.ru (Playwright, данные из карточек страницы поиска) ────────────────

    def _crawl_hh(self, page, keyword: str, city: Optional[str], known_urls: set[str] = set()) -> list[dict]:
        from playwright.sync_api import TimeoutError as PWTimeout

        area = HH_CITY_IDS.get(city.strip().lower(), HH_DEFAULT_AREA) if city else HH_DEFAULT_AREA
        results = []

        for page_num in range(MAX_PAGES):
            url = f"https://hh.ru/search/vacancy?text={quote_plus(keyword)}&area={area}&page={page_num}"
            self._log(f"[hh] стр.{page_num + 1}/{MAX_PAGES}: {url}")
            page_start = time.time()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            except Exception as e:
                self._log(f"[hh] ошибка загрузки стр.{page_num + 1}: {e}")
                break

            try:
                page.wait_for_selector(
                    "[data-qa='vacancy-serp__results'], [data-qa='vacancy-serp__results-empty']",
                    timeout=15_000,
                )
            except PWTimeout:
                self._log(f"[hh] контент не загрузился на стр.{page_num + 1}")
                break

            # Прокручиваем страницу, чтобы подгрузились все карточки
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            cards: list[dict] = page.evaluate("""
                () => Array.from(
                    document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]')
                ).map(card => {
                    const q = sel => {
                        const el = card.querySelector(sel);
                        return el ? el.innerText.trim() : null;
                    };
                    const link = card.querySelector('a[data-qa="serp-item__title"]');
                    return {
                        url:         link ? link.href : null,
                        title:       link ? link.innerText.trim() : null,
                        company:     q('[data-qa="vacancy-serp__vacancy-employer-name"]'),
                        salary_raw:  q('[data-qa="vacancy-serp__vacancy-compensation"]'),
                        city:        q('[data-qa="vacancy-serp__vacancy-workplace-text"]')
                                  || q('[data-qa="vacancy-serp__vacancy-address"]'),
                        description: q('[data-qa="vacancy-serp__vacancy-cut-description"]')
                                  || q('[data-qa="vacancy-serp__vacancy_snippet"]'),
                    };
                }).filter(v => v.url)
            """)

            page_elapsed = time.time() - page_start
            self._log(f"[hh] найдено карточек: {len(cards)} за {page_elapsed:.1f}с")
            if not cards:
                break

            for card in cards:
                salary_from, salary_to = _parse_salary(card.get("salary_raw"))
                results.append({
                    "url":          card["url"],
                    "title":        card["title"],
                    "company":      card.get("company"),
                    "city":         card.get("city"),
                    "description":  card.get("description"),
                    "salary_from":  salary_from,
                    "salary_to":    salary_to,
                    "published_at": None,
                })
                self._log(f"[hh] ✓ {card.get('title', '?')[:60]}")

            if not page.query_selector("a[data-qa='pager-next']"):
                break
            self._delay()

        if FETCH_DESCRIPTIONS and results:
            new_results = [r for r in results if r["url"] not in known_urls]
            skipped = len(results) - len(new_results)
            if skipped:
                self._log(f"[hh] фаза 2: пропущено {skipped} дублей, загружаем {len(new_results)} описаний...")
            else:
                self._log(f"[hh] фаза 2: {len(new_results)} описаний...")
            if new_results:
                self._fetch_hh_descriptions(page, new_results)

        return results

    # ── superjob.ru (Playwright, данные из карточек страницы поиска) ──────────

    def _crawl_superjob(self, page, keyword: str, city: Optional[str], known_urls: set[str] = set()) -> list[dict]:
        from playwright.sync_api import TimeoutError as PWTimeout

        city_id = None
        if city:
            city_id = SUPERJOB_CITY_IDS.get(city.strip().lower())
            if city_id is None:
                self._log(
                    f"[superjob] ⚠ город '{city}' не найден в SUPERJOB_CITY_IDS — "
                    f"поиск будет по всей России. Доступны: {', '.join(SUPERJOB_CITY_IDS)}"
                )
        results = []

        for page_num in range(1, MAX_PAGES + 1):
            encoded_kw = quote_plus(keyword)
            if city_id:
                url = (
                    f"https://www.superjob.ru/vacancy/search/"
                    f"?keywords={encoded_kw}&geo[c][0]={city_id}&page={page_num}"
                )
            else:
                url = f"https://www.superjob.ru/vacancy/search/?keywords={encoded_kw}&page={page_num}"
            self._log(f"[superjob] стр.{page_num}/{MAX_PAGES}: {url}")
            page_start = time.time()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            except Exception as e:
                self._log(f"[superjob] ошибка загрузки стр.{page_num}: {e}")
                break

            try:
                page.wait_for_selector(".f-test-search-result-item", timeout=15_000)
            except PWTimeout:
                self._log(f"[superjob] контент не загрузился на стр.{page_num}")
                break

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            cards: list[dict] = page.evaluate("""
                () => Array.from(
                    document.querySelectorAll('.f-test-search-result-item')
                ).map(card => {
                    const q = sel => {
                        const el = card.querySelector(sel);
                        return el ? el.innerText.trim() : null;
                    };
                    const link = [...card.querySelectorAll('a[href*="/vakansii/"]')]
                        .find(a => a.href !== window.location.origin + '/vakansii/');
                    const snippet = card.querySelector('[class*="f-test-pseudolink-"]');
                    const datePattern = /^\\d{1,2}\\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)$/i;
                    const dateEl = [...card.querySelectorAll('span')].find(
                        el => !el.children.length && el.innerText && datePattern.test(el.innerText.trim())
                    );
                    return {
                        url:        link ? link.href : null,
                        title:      link ? link.innerText.trim() : null,
                        company:    q('.f-test-text-vacancy-item-company-name'),
                        salary_raw: q('.f-test-text-company-item-salary'),
                        city:       q('.f-test-text-company-item-location'),
                        description: snippet ? snippet.innerText.trim() : null,
                        date_raw:   dateEl ? dateEl.innerText.trim() : null,
                    };
                }).filter(v => v.url)
            """)

            page_elapsed = time.time() - page_start
            self._log(f"[superjob] найдено карточек: {len(cards)} за {page_elapsed:.1f}с")
            if not cards:
                break

            for card in cards:
                salary_from, salary_to = _parse_salary(card.get("salary_raw"))
                city_raw = card.get("city")
                results.append({
                    "url":          card["url"],
                    "title":        card["title"],
                    "company":      card.get("company"),
                    "city":         city_raw.split(",")[0].strip() if city_raw else None,
                    "description":  card.get("description"),
                    "salary_from":  salary_from,
                    "salary_to":    salary_to,
                    "published_at": _parse_ru_date(card.get("date_raw")),
                })
                self._log(f"[superjob] ✓ {card.get('title', '?')[:60]}")

            if not page.query_selector(".f-test-link-Dalshe"):
                break
            self._delay()

        if FETCH_DESCRIPTIONS and results:
            new_results = [r for r in results if r["url"] not in known_urls]
            skipped = len(results) - len(new_results)
            if skipped:
                self._log(f"[superjob] фаза 2: пропущено {skipped} дублей, загружаем {len(new_results)} новых описаний...")
            else:
                self._log(f"[superjob] фаза 2: {len(new_results)} описаний (блокировка ресурсов)...")
            if new_results:
                descs = self._fetch_descriptions(page, [r["url"] for r in new_results], tag="superjob")
                for item in new_results:
                    desc = descs.get(item["url"])
                    if desc:
                        item["description"] = desc

        return results

    # ── career.habr.com ───────────────────────────────────────────────────────

    def _crawl_habr(self, page, keyword: str, city: Optional[str], known_urls: set[str] = set()) -> list[dict]:
        from playwright.sync_api import TimeoutError as PWTimeout

        city_code = None
        if city:
            city_code = HABR_CITY_IDS.get(city.strip().lower())
            if city_code is None:
                self._log(
                    f"[habr] ⚠ город '{city}' не найден в HABR_CITY_IDS — "
                    f"поиск по всей России. Доступны: {', '.join(HABR_CITY_IDS)}"
                )
        results = []

        for page_num in range(1, MAX_PAGES + 1):
            encoded_kw = quote_plus(keyword)
            url = f"https://career.habr.com/vacancies?q={encoded_kw}&type=all&page={page_num}"
            if city_code:
                url += f"&locations[]={city_code}"
            self._log(f"[habr] стр.{page_num}/{MAX_PAGES}: {url}")
            page_start = time.time()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            except Exception as e:
                self._log(f"[habr] ошибка загрузки стр.{page_num}: {e}")
                break

            try:
                page.wait_for_selector(
                    ".vacancy-card, .empty-placeholder",
                    timeout=15_000,
                )
            except PWTimeout:
                self._log(f"[habr] контент не загрузился на стр.{page_num}")
                break

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            cards: list[dict] = page.evaluate("""
                () => Array.from(
                    document.querySelectorAll('.vacancy-card')
                ).map(card => {
                    const q = sel => {
                        const el = card.querySelector(sel);
                        return el ? el.innerText.trim() : null;
                    };
                    const link = card.querySelector('.vacancy-card__title a');
                    const href = link ? link.getAttribute('href') : null;
                    const fullUrl = href
                        ? (href.startsWith('http') ? href : 'https://career.habr.com' + href)
                        : null;
                    const metaEl = card.querySelector('.vacancy-card__meta');
                    const metaText = metaEl ? metaEl.innerText.trim() : null;
                    return {
                        url:        fullUrl,
                        title:      link ? link.innerText.trim() : null,
                        company:    q('.vacancy-card__company-title') || q('.vacancy-card__company a'),
                        salary_raw: q('.vacancy-card__salary'),
                        meta:       metaText,
                    };
                }).filter(v => v.url)
            """)

            page_elapsed = time.time() - page_start
            self._log(f"[habr] найдено карточек: {len(cards)} за {page_elapsed:.1f}с")
            if not cards:
                break

            for card in cards:
                salary_from, salary_to = _parse_salary(card.get("salary_raw"))
                meta = card.get("meta") or ""
                # meta usually: "City · Skill · ..."  or  "Remote · ..."
                city_val = meta.split("·")[0].strip() if "·" in meta else None
                results.append({
                    "url":          card["url"],
                    "title":        card["title"],
                    "company":      card.get("company"),
                    "city":         city_val,
                    "description":  None,
                    "salary_from":  salary_from,
                    "salary_to":    salary_to,
                    "published_at": None,
                })
                self._log(f"[habr] ✓ {card.get('title', '?')[:60]}")

            # check next page: habr uses numbered pagination, stop when no more cards or limit reached
            next_btn = page.query_selector(".pagination__page--next, a[rel='next']")
            if not next_btn:
                break
            self._delay()

        if FETCH_DESCRIPTIONS and results:
            _WAIT = ".vacancy-description, .vacancy-description__text"
            _JS = """() => {
                const el = document.querySelector('.vacancy-description__text')
                        || document.querySelector('.vacancy-description');
                return el ? el.innerText.trim() : null;
            }"""
            new_results = [r for r in results if r["url"] not in known_urls]
            skipped = len(results) - len(new_results)
            if skipped:
                self._log(f"[habr] фаза 2: пропущено {skipped} дублей, загружаем {len(new_results)} описаний...")
            else:
                self._log(f"[habr] фаза 2: {len(new_results)} описаний...")
            if new_results:
                descs = self._fetch_descriptions(
                    page,
                    [r["url"] for r in new_results],
                    wait_selector=_WAIT,
                    extract_js=_JS,
                    tag="habr",
                )
                for item in new_results:
                    desc = descs.get(item["url"])
                    if desc:
                        item["description"] = desc

        return results

    # ── description fetching ──────────────────────────────────────────────────

    def _fetch_hh_descriptions(self, page, results: list[dict]) -> None:
        from src.job_radar.services.parser import parse_hh_vacancy

        _BLOCK = "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot,otf,mp4,avi,webm}"

        def _abort(route):
            route.abort()

        page.route(_BLOCK, _abort)

        total = len(results)
        for i, item in enumerate(results, 1):
            url = item["url"]
            slug = url[url.rfind("/") + 1:][:50]
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25_000)
                try:
                    page.wait_for_selector("[data-qa='vacancy-description']", timeout=6_000)
                except Exception:
                    self._log(f"[hh] описание {i}/{total}: — {slug}")
                    continue
                parsed = parse_hh_vacancy(page.content())
                if parsed.get("description"):
                    item["description"] = parsed["description"]
                if parsed.get("published_at"):
                    item["published_at"] = parsed["published_at"]
                if parsed.get("city"):
                    item["city"] = parsed["city"]
                if not item.get("salary_from") and parsed.get("salary_from"):
                    item["salary_from"] = parsed["salary_from"]
                if not item.get("salary_to") and parsed.get("salary_to"):
                    item["salary_to"] = parsed["salary_to"]
                self._log(f"[hh] описание {i}/{total}: {'✓' if parsed.get('description') else '—'} {slug}")
            except Exception as e:
                self._log(f"[hh] описание {i}/{total}: ошибка — {e}")

        page.unroute(_BLOCK, _abort)

    def _fetch_descriptions(
        self,
        page,
        urls: list[str],
        wait_selector: str = "div[class=''] > span > span",
        extract_js: str = """() => {
            // superjob: CSS Modules — target DOM structure only
            const el = document.querySelector('div[class=""] > span > span');
            if (el && el.innerText.trim().length > 50) return el.innerText.trim();
            let best = null, bestLen = 50;
            for (const span of document.querySelectorAll('span')) {
                if (span.querySelector(':scope > ul')) {
                    const t = span.innerText.trim();
                    if (t.length > bestLen) { best = t; bestLen = t.length; }
                }
            }
            return best;
        }""",
        tag: str = "superjob",
    ) -> dict[str, Optional[str]]:
        _BLOCK = "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot,otf,mp4,avi,webm}"

        def _abort(route):
            route.abort()

        page.route(_BLOCK, _abort)

        results: dict[str, Optional[str]] = {}
        total = len(urls)
        for i, url in enumerate(urls, 1):
            slug = url[url.rfind("/") + 1:][:50]
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25_000)
                try:
                    page.wait_for_selector(wait_selector, timeout=6_000)
                except Exception:
                    results[url] = None
                    self._log(f"[{tag}] описание {i}/{total}: — {slug}")
                    continue
                desc = page.evaluate(extract_js)
                results[url] = desc
                self._log(f"[{tag}] описание {i}/{total}: {'✓' if desc else '—'} {slug}")
            except Exception as e:
                results[url] = None
                self._log(f"[{tag}] описание {i}/{total}: ошибка — {e}")

        page.unroute(_BLOCK, _abort)
        return results

    # ── helpers ───────────────────────────────────────────────────────────────

    def _delay(self) -> None:
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


_MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def _parse_ru_date(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    parts = text.strip().lower().split()
    if len(parts) == 2:
        day_str, month_name = parts
        month = _MONTHS_RU.get(month_name)
        if month and day_str.isdigit():
            try:
                return datetime(datetime.now().year, month, int(day_str))
            except ValueError:
                return None
    return None


def _parse_salary(raw: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not raw:
        return None, None
    text = raw.replace(" ", "").replace(" ", "").lower()
    numbers = [int(n) for n in re.findall(r"\d+", text)]
    if not numbers:
        return None, None
    if "от" in text and "до" in text and len(numbers) >= 2:
        return numbers[0], numbers[1]
    if "от" in text:
        return numbers[0], None
    if "до" in text:
        return None, numbers[0]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    return numbers[0], numbers[0]
