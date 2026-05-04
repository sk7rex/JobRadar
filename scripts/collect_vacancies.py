#!/usr/bin/env python3
"""
Массовый сбор вакансий с superjob.ru до достижения 20 000 вакансий с описаниями.

Запуск из корня проекта:
    python scripts/collect_vacancies.py

Перед запуском убедитесь:
  - БД инициализирована:  python -m job_radar.main init
  - MAX_PAGES в config.py >= 14
  - FETCH_DESCRIPTIONS = True в config.py
  - HEADLESS = True в config.py для фонового сбора

Прерывание: Ctrl+C — завершит текущий таск и остановится.
"""

import signal
import sys
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func
from sqlmodel import select

from src.job_radar.config import MAX_PAGES
from src.job_radar.database import init_db, get_session
from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.vacancy import Vacancy
from src.job_radar.services.crawler import JobCrawler
from src.job_radar.services.manager import TaskManager

TARGET = 20_000
SOURCE = "superjob"
TASK_DELAY = 15  # пауза между тасками (сек)

# Каждый элемент — строка (без города) или кортеж (keyword, city).
# Городские вариации дают отдельную выдачу — снижают пересечения.
KEYWORDS: list[str | tuple[str, str]] = [
    # ── IT (минимальный набор, без синонимов) ──────────────────────────────
    "1с разработчик",
    "системный администратор",
    "тестировщик",
    "devops инженер",
    "аналитик данных",
    "сетевой инженер",
    "it специалист",
    "технический поддержки",
    ("разработчик", "москва"),
    ("разработчик", "санкт-петербург"),
    # ── Финансы ────────────────────────────────────────────────────────────
    "бухгалтер",
    "главный бухгалтер",
    "финансовый аналитик",
    "экономист",
    "аудитор",
    "финансовый директор",
    "казначей",
    "финансовый менеджер",
    "налоговый консультант",
    "финансовый контролер",
    ("бухгалтер", "москва"),
    ("бухгалтер", "санкт-петербург"),
    ("экономист", "москва"),
    ("экономист", "санкт-петербург"),
    # ── Продажи ────────────────────────────────────────────────────────────
    "менеджер по продажам",
    "торговый представитель",
    "директор по продажам",
    "менеджер по работе с клиентами",
    "руководитель отдела продаж",
    "менеджер по развитию бизнеса",
    "коммерческий директор",
    ("менеджер по продажам", "москва"),
    ("менеджер по продажам", "санкт-петербург"),
    ("торговый представитель", "москва"),
    ("торговый представитель", "санкт-петербург"),
    # ── Маркетинг ──────────────────────────────────────────────────────────
    "маркетолог",
    "smm менеджер",
    "таргетолог",
    "pr менеджер",
    "бренд менеджер",
    "директор по маркетингу",
    "интернет маркетолог",
    "контент менеджер",
    "seo специалист",
    ("маркетолог", "москва"),
    ("маркетолог", "санкт-петербург"),
    # ── HR ─────────────────────────────────────────────────────────────────
    "рекрутер",
    "hr менеджер",
    "специалист по кадрам",
    "менеджер по персоналу",
    "hr бизнес партнер",
    "hr директор",
    "специалист по обучению",
    ("рекрутер", "москва"),
    # ── Юриспруденция ──────────────────────────────────────────────────────
    "юрист",
    "юрисконсульт",
    "корпоративный юрист",
    "помощник юриста",
    "адвокат",
    ("юрист", "москва"),
    ("юрист", "санкт-петербург"),
    # ── Инженерия ──────────────────────────────────────────────────────────
    "инженер конструктор",
    "инженер технолог",
    "инженер пто",
    "инженер проектировщик",
    "главный инженер",
    "инженер по охране труда",
    "инженер по качеству",
    "инженер сметчик",
    "технолог",
    ("инженер", "москва"),
    ("инженер", "санкт-петербург"),
    ("технолог", "москва"),
    # ── Строительство ──────────────────────────────────────────────────────
    "прораб",
    "начальник участка",
    "инженер строитель",
    "архитектор",
    "проектировщик",
    "дизайнер интерьеров",
    "сметчик",
    ("прораб", "москва"),
    ("архитектор", "москва"),
    # ── Производство и рабочие специальности ───────────────────────────────
    "электрик",
    "сварщик",
    "слесарь",
    "токарь",
    "оператор производства",
    "монтажник",
    "наладчик оборудования",
    "механик",
    "электромонтажник",
    "фрезеровщик",
    ("электрик", "москва"),
    ("сварщик", "москва"),
    # ── Логистика и транспорт ──────────────────────────────────────────────
    "логист",
    "водитель",
    "кладовщик",
    "экспедитор",
    "диспетчер",
    "менеджер по закупкам",
    "начальник склада",
    "менеджер по логистике",
    "специалист вэд",
    ("водитель", "москва"),
    ("водитель", "санкт-петербург"),
    ("кладовщик", "москва"),
    ("логист", "москва"),
    # ── Медицина ───────────────────────────────────────────────────────────
    "врач",
    "педиатр",
    "терапевт",
    "хирург",
    "стоматолог",
    "медсестра",
    "фармацевт",
    "фельдшер",
    "провизор",
    "психолог",
    ("врач", "москва"),
    ("врач", "санкт-петербург"),
    ("медсестра", "москва"),
    ("фармацевт", "москва"),
    # ── Образование ────────────────────────────────────────────────────────
    "учитель",
    "преподаватель",
    "воспитатель",
    "педагог",
    "учитель математики",
    "учитель английского языка",
    "логопед",
    "тренер",
    "инструктор",
    ("учитель", "москва"),
    ("воспитатель", "москва"),
    # ── Административные ───────────────────────────────────────────────────
    "офис менеджер",
    "секретарь",
    "администратор",
    "помощник руководителя",
    "делопроизводитель",
    "оператор колл центра",
    ("администратор", "москва"),
    # ── Банки и страхование ────────────────────────────────────────────────
    "кредитный специалист",
    "операционист",
    "финансовый консультант",
    "страховой агент",
    "андеррайтер",
    "менеджер банка",
    ("кредитный специалист", "москва"),
    # ── Недвижимость ───────────────────────────────────────────────────────
    "риелтор",
    "агент по недвижимости",
    "оценщик",
    "управляющий недвижимостью",
    ("риелтор", "москва"),
    ("риелтор", "санкт-петербург"),
    # ── Торговля и ритейл ──────────────────────────────────────────────────
    "управляющий магазином",
    "директор магазина",
    "товаровед",
    "мерчандайзер",
    "продавец консультант",
    ("продавец консультант", "москва"),
    ("мерчандайзер", "москва"),
    # ── Общепит ────────────────────────────────────────────────────────────
    "повар",
    "шеф повар",
    "технолог пищевой промышленности",
    "кондитер",
    "су шеф",
    ("повар", "москва"),
    ("повар", "санкт-петербург"),
    # ── Охрана и безопасность ──────────────────────────────────────────────
    "охранник",
    "начальник охраны",
    "специалист по информационной безопасности",
    "специалист по охране труда",
    # ── Управление ─────────────────────────────────────────────────────────
    "руководитель проекта",
    "операционный директор",
    "генеральный директор",
    "директор по развитию",
    "исполнительный директор",
    ("руководитель проекта", "москва"),
]

_stop = False


def _on_sigint(signum, frame):
    global _stop
    print("\n[!] Прерывание — завершаем текущий таск и останавливаемся...", flush=True)
    _stop = True


def _count_with_descriptions() -> int:
    with get_session() as session:
        return session.exec(
            select(func.count(Vacancy.id)).where(
                Vacancy.description.isnot(None),
                Vacancy.description != "",
            )
        ).one()


def _is_completed(keyword: str, city: Optional[str] = None) -> bool:
    """True если этот keyword+city+superjob уже успешно отработал."""
    with get_session() as session:
        source = session.exec(select(Source).where(Source.name == SOURCE)).first()
        if not source:
            return False
        query = select(SearchTask).where(
            SearchTask.keyword == keyword.strip().lower(),
            SearchTask.source_id == source.id,
            SearchTask.status == TaskStatus.COMPLETED,
        )
        if city:
            query = query.where(SearchTask.city == city)
        else:
            query = query.where(SearchTask.city.is_(None))
        return bool(session.exec(query).first())


def main() -> None:
    signal.signal(signal.SIGINT, _on_sigint)
    init_db()

    max_possible = len(KEYWORDS) * MAX_PAGES * 20
    print(f"Цель:           {TARGET:,} вакансий с описаниями")
    print(f"Ключевых слов:  {len(KEYWORDS)}")
    print(f"MAX_PAGES:      {MAX_PAGES}  (~{max_possible:,} вакансий максимум)")
    if max_possible < TARGET:
        print(
            f"\n[!] При MAX_PAGES={MAX_PAGES} и {len(KEYWORDS)} записях максимум ~{max_possible:,}.\n"
            f"    Увеличьте MAX_PAGES до "
            f"{-(-TARGET // (len(KEYWORDS) * 20))} или добавьте ключевых слов.\n"
        )

    session_start = time.time()

    for idx, entry in enumerate(KEYWORDS, 1):
        if _stop:
            break

        count = _count_with_descriptions()
        if count >= TARGET:
            break

        keyword, city = (entry[0], entry[1]) if isinstance(entry, tuple) else (entry, None)
        label = f"'{keyword}'" + (f" [{city}]" if city else "")
        remaining = TARGET - count
        print(
            f"\n[{count:>6,}/{TARGET:,}] осталось {remaining:,} | "
            f"({idx}/{len(KEYWORDS)}) {label}",
            flush=True,
        )

        if _is_completed(keyword, city):
            print("  → уже выполнено, пропуск")
            continue

        task_id: int | None = None
        with get_session() as session:
            manager = TaskManager(session)
            try:
                task = manager.create_task(keyword, SOURCE, city=city)
                task_id = task.id
                manager.update_task_status(task_id, "in_progress")
            except ValueError as e:
                print(f"  → {e}")
                continue

        saved = skipped = errors = with_desc = 0
        try:
            with get_session() as session:
                known_urls = set(session.exec(select(Vacancy.url)).all())

            crawler = JobCrawler(
                headless=True,
                log=lambda msg: print(f"  {msg}", flush=True),
            )
            t0 = time.time()
            vacancies = crawler.crawl(keyword, SOURCE, city=city, known_urls=known_urls)
            elapsed = time.time() - t0

            with get_session() as session:
                manager = TaskManager(session)
                for v in vacancies:
                    try:
                        manager.save_parsed_vacancy(task_id, v)
                        saved += 1
                        if v.get("description"):
                            with_desc += 1
                    except ValueError:
                        skipped += 1
                    except Exception:
                        errors += 1
                manager.update_task_status(task_id, "completed")

            m, s = divmod(int(elapsed), 60)
            print(
                f"  ✓ {m}м {s}с | "
                f"сохранено: {saved} | с описанием: {with_desc} | "
                f"дубли: {skipped} | ошибки: {errors}",
                flush=True,
            )

        except Exception as e:
            print(f"  ✗ Краулер упал: {e}", flush=True)
            if task_id:
                with get_session() as session:
                    manager = TaskManager(session)
                    try:
                        manager.update_task_status(task_id, "failed")
                    except Exception:
                        pass

        if not _stop:
            print(f"  → пауза {TASK_DELAY}с...", flush=True)
            time.sleep(TASK_DELAY)

    final = _count_with_descriptions()
    total_elapsed = time.time() - session_start
    hh, rem = divmod(int(total_elapsed), 3600)
    mm, ss = divmod(rem, 60)

    print(f"\n{'─' * 50}")
    if final >= TARGET:
        print(f"✓ Цель достигнута: {final:,}/{TARGET:,} вакансий с описаниями")
    else:
        print(f"⚠ Цель не достигнута: {final:,}/{TARGET:,}")
        print("  Добавьте ключевых слов или увеличьте MAX_PAGES в config.py")
    print(f"Суммарное время: {hh}ч {mm}м {ss}с")


if __name__ == "__main__":
    main()
