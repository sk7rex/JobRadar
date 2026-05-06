import shlex
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.job_radar.database import init_db, get_session
from src.job_radar.models.task import TaskStatus
from src.job_radar.services.manager import TaskManager

app = typer.Typer(help="Job Radar Manager CLI")
console = Console()


# --- ВНУТРЕННИЕ ФУНКЦИИ ---

def _init_db_command() -> None:
    try:
        status = init_db()
        if status == "created":
            console.print("[bold green][OK] База данных успешно инициализирована![/bold green]")
        elif status == "exists":
            console.print("[bold yellow][WARNING] База данных уже инициализирована[/bold yellow]")

    except Exception as e:
        console.print(f"[bold red][ERROR] Ошибка инициализации:[/bold red] {e}")


def _add_task_command(keyword: str, source: str, city: Optional[str] = None) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        try:
            task = manager.create_task(keyword, source, city)
            src_name = task.source_relation.name if task.source_relation else source
            city_label = f" | Город: [cyan]{task.city}[/cyan]" if task.city else ""
            console.print(
                f"[green][OK] Задача создана![/green] "
                f"ID: [bold]{task.id}[/bold] | "
                f"Ищем: [magenta]{task.keyword}[/magenta] @ [blue]{src_name}[/blue]"
                f"{city_label}"
            )
        except ValueError as e:
            console.print(f"[bold red]Ошибка:[/bold red] {e}")
        except Exception as e:
            console.print(f"[bold red]Неожиданная ошибка:[/bold red] {e}")


def _add_source_command(name: str, url: str) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        try:
            src = manager.add_source(name, url)
            console.print(f"[green]✔ Источник добавлен![/green] ID: {src.id}, Name: {src.name}, URL: {src.url}")
        except Exception as e:
            console.print(f"[bold red]Ошибка:[/bold red] {e}")


def _set_status_command(task_id: int, new_status: str) -> None:
    """Изменяет статус задачи через менеджер."""
    with get_session() as session:
        manager = TaskManager(session)
        try:
            task = manager.update_task_status(task_id, new_status)
            console.print(f"[green]✔ Статус задачи {task_id} изменен на [bold]{task.status.value}[/bold][/green]")
        except ValueError as e:
            console.print(f"[bold red]Ошибка:[/bold red] {e}")
        except Exception as e:
            console.print(f"[bold red]Неожиданная ошибка:[/bold red] {e}")


def _delete_task_command(task_id: int) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        try:
            if manager.delete_task(task_id):
                console.print(f"[green]✔ Задача {task_id} удалена.[/green]")
            else:
                console.print(f"[red]Task {task_id} not found.[/red]")
        except Exception as e:
            console.print(f"[bold red]Ошибка удаления:[/bold red] {e}")


def _toggle_source_command(name: str, active: bool) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        try:
            src = manager.toggle_source(name, active)
            state = "[green]включён[/green]" if active else "[red]отключён[/red]"
            console.print(f"[green]✔[/green] Источник [bold]{src.name}[/bold] {state}.")
        except ValueError as e:
            console.print(f"[bold red]Ошибка:[/bold red] {e}")


def _delete_source_command(name: str) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        try:
            manager.delete_source(name)
            console.print(f"[green]✔ Источник {name} удален.[/green]")
        except Exception as e:
            console.print(f"[bold red]Ошибка:[/bold red] {e}")


def _list_tasks_command(limit: int = 10) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        tasks = manager.list_tasks(limit)

        if not tasks:
            console.print("[yellow]Очередь задач пуста.[/yellow]")
            return

        table = Table(title=f"Задачи (последние {limit})")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Запрос", style="magenta")
        table.add_column("Источник", style="blue")
        table.add_column("Статус", justify="center")
        table.add_column("Найдено")
        table.add_column("Создано", style="dim")

        for task in tasks:
            status_color = {
                TaskStatus.NEW: "yellow",
                TaskStatus.IN_PROGRESS: "blue",
                TaskStatus.COMPLETED: "green",
                TaskStatus.FAILED: "red"
            }.get(task.status, "white")

            src_name = task.source_relation.name if task.source_relation else "?"

            table.add_row(
                str(task.id),
                task.keyword,
                src_name,
                f"[{status_color}]{task.status.value}[/{status_color}]",
                str(task.items_found),
                task.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        console.print(table)


def _list_sources_command() -> None:
    with get_session() as session:
        manager = TaskManager(session)
        sources = manager.list_sources()

        table = Table(title="Источники данных")
        table.add_column("ID", style="cyan")
        table.add_column("Название", style="bold green")
        table.add_column("URL")
        table.add_column("Активен", justify="center")

        for src in sources:
            active_icon = "✅" if src.is_active else "❌"
            table.add_row(str(src.id), src.name, src.url, active_icon)

        console.print(table)


def _show_task_stats_command(task_id: int) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        stats = manager.get_task_stats(task_id)
        if not stats:
            console.print(f"[red]Задача с ID {task_id} не найдена.[/red]")
            return

        task = stats["task"]
        total = stats["total"]
        console.print(f"\n[bold]Статистика задачи #{task_id}[/bold] — {task.keyword} @ {task.source_id}")

        if total == 0:
            console.print("[yellow]Вакансий нет.[/yellow]")
            return

        def pct(n): return f"{n}/{total} ({100 * n // total}%)"

        # Полнота данных
        completeness = Table(title="Полнота данных", show_header=False, box=None)
        completeness.add_column("", style="cyan", justify="right")
        completeness.add_column("", style="white")
        completeness.add_row("Всего вакансий", str(total))
        completeness.add_row("С зарплатой",   pct(stats["with_salary"]))
        completeness.add_row("С городом",      pct(stats["with_city"]))
        completeness.add_row("С датой",        pct(stats["with_date"]))
        completeness.add_row("С описанием",    pct(stats["with_description"]))
        console.print(completeness)

        # Зарплаты
        if stats["salary_min"] is not None:
            salary_table = Table(title="Зарплаты (руб.)", show_header=False, box=None)
            salary_table.add_column("", style="cyan", justify="right")
            salary_table.add_column("", style="green")
            salary_table.add_row("Минимум", f"{stats['salary_min']:,}")
            salary_table.add_row("Медиана", f"{stats['salary_median']:,}")
            salary_table.add_row("Максимум", f"{stats['salary_max']:,}")
            console.print(salary_table)

        # Даты
        if stats["date_min"] is not None:
            date_table = Table(title="Даты публикации", show_header=False, box=None)
            date_table.add_column("", style="cyan", justify="right")
            date_table.add_column("", style="white")
            date_table.add_row("Самая старая", stats["date_min"].strftime("%d.%m.%Y"))
            date_table.add_row("Самая свежая", stats["date_max"].strftime("%d.%m.%Y"))
            console.print(date_table)

        # Топ компаний
        if stats["top_companies"]:
            companies_table = Table(title="Топ компаний", show_header=False, box=None)
            companies_table.add_column("", style="yellow")
            companies_table.add_column("", style="dim", justify="right")
            for company, count in stats["top_companies"]:
                companies_table.add_row(company, str(count))
            console.print(companies_table)


def _show_vacancy_command(vacancy_id: int) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        v = manager.get_vacancy(vacancy_id)
        if not v:
            console.print(f"[red]Вакансия с ID {vacancy_id} не найдена.[/red]")
            return

        table = Table(show_header=False, box=None, title=f"Вакансия #{v.id}")
        table.add_column("Поле", style="cyan", justify="right")
        table.add_column("Значение", style="white")

        salary = "—"
        if v.salary_from: salary = f"от {v.salary_from}"
        if v.salary_to: salary += f" до {v.salary_to}"

        table.add_row("ID", str(v.id))
        table.add_row("Task ID", str(v.task_id))
        table.add_row("Должность", v.title or "—")
        table.add_row("Компания", v.company or "—")
        table.add_row("Город", v.city or "—")
        table.add_row("Зарплата", salary)
        table.add_row("Дата публ.", str(v.published_at) if v.published_at else "—")
        table.add_row("URL", v.url or "—")
        table.add_row("Путь к HTML", v.file_path or "—")
        desc = (v.description[:200] + "...") if v.description and len(v.description) > 200 else (v.description or "—")
        table.add_row("Описание", desc)

        console.print(table)


def _list_task_vacancies_command(task_id: int) -> None:
    from src.job_radar.models.task import SearchTask
    with get_session() as session:
        manager = TaskManager(session)
        task = session.get(SearchTask, task_id)
        if not task:
            console.print(f"[red]Задача с ID {task_id} не найдена.[/red]")
            return

        vacancies = manager.list_vacancies_by_task(task_id)
        if not vacancies:
            console.print(f"[yellow]По задаче #{task_id} вакансий нет.[/yellow]")
            return

        table = Table(title=f"Вакансии задачи #{task_id} ({task.keyword}), всего: {len(vacancies)}")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Должность", style="bold white")
        table.add_column("Компания", style="yellow")
        table.add_column("Город", style="green")
        table.add_column("Зарплата", style="magenta")
        table.add_column("URL", style="dim", no_wrap=True)

        for v in vacancies:
            salary = "—"
            if v.salary_from:
                salary = f"от {v.salary_from}"
            if v.salary_to:
                salary += f" до {v.salary_to}"

            table.add_row(
                str(v.id),
                v.title[:45] if v.title else "—",
                v.company[:30] if v.company else "—",
                v.city or "—",
                salary,
                v.url[:50] if v.url else "—",
            )
        console.print(table)


def _list_vacancies_command(limit: int = 10) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        vacancies = manager.list_vacancies(limit)

        if not vacancies:
            console.print("[yellow]Вакансий пока нет.[/yellow]")
            return

        table = Table(title=f"Последние вакансии (Top {limit})")
        table.add_column("ID", style="cyan")
        table.add_column("Должность", style="bold white")
        table.add_column("Компания", style="yellow")
        table.add_column("Зарплата", style="green")
        table.add_column("TaskID", style="dim")

        for v in vacancies:
            salary = "—"
            if v.salary_from: salary = f"от {v.salary_from}"
            if v.salary_to: salary += f" до {v.salary_to}"

            table.add_row(str(v.id), v.title[:50], v.company or "—", salary, str(v.task_id))
        console.print(table)


def _list_logs_command(limit: int = 20) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        logs = manager.list_logs(limit)

        if not logs:
            console.print("[yellow]Логов пока нет.[/yellow]")
            return

        table = Table(title=f"Системные логи (Последние {limit})")
        table.add_column("Time", style="dim")
        table.add_column("Level", width=10)
        table.add_column("TaskID")
        table.add_column("Message")

        for log in logs:
            level_style = "white"
            if log.level == "ERROR":
                level_style = "bold red"
            elif log.level == "WARNING":
                level_style = "yellow"
            elif log.level == "INFO":
                level_style = "green"

            table.add_row(
                log.created_at.strftime("%H:%M:%S"),
                f"[{level_style}]{log.level}[/{level_style}]",
                str(log.task_id),
                log.message
            )
        console.print(table)


def _run_tasks_command(task_id: Optional[int] = None, headless: bool = True) -> None:
    from sqlalchemy.orm import selectinload
    from sqlmodel import select

    from src.job_radar.models.task import SearchTask
    from src.job_radar.services.crawler import JobCrawler

    with get_session() as session:
        manager = TaskManager(session)

        if task_id is not None:
            task = session.exec(
                select(SearchTask)
                .options(selectinload(SearchTask.source_relation))
                .where(SearchTask.id == task_id)
            ).first()
            if not task:
                console.print(f"[red]Задача {task_id} не найдена.[/red]")
                return
            tasks = [task]
        else:
            tasks = manager.get_pending_tasks()

        if not tasks:
            console.print("[yellow]Нет задач со статусом NEW.[/yellow]")
            return

        def _crawler_log(msg: str) -> None:
            console.print(f"  [dim]{msg}[/dim]")

        crawler = JobCrawler(headless=headless, log=_crawler_log)

        for task in tasks:
            source_name = task.source_relation.name if task.source_relation else ""
            city = task.city
            label = f"[bold]#{task.id}[/bold] {task.keyword} @ {source_name}"
            if city:
                label += f" [{city}]"
            console.print(f"\nЗадача {label}")

            try:
                manager.update_task_status(task.id, "in_progress")
            except ValueError as e:
                console.print(f"  [red]Нельзя запустить: {e}[/red]")
                continue

            try:
                import time as _time
                from collections import Counter

                console.print("  [yellow]Запуск браузера...[/yellow]")
                run_start = _time.time()
                vacancies = crawler.crawl(task.keyword, source_name, city)
                elapsed = _time.time() - run_start

                saved = skipped = errors = 0
                for v in vacancies:
                    try:
                        manager.save_parsed_vacancy(task.id, v)
                        saved += 1
                    except ValueError:
                        skipped += 1
                    except Exception:
                        errors += 1

                manager.update_task_status(task.id, "completed")

                total = len(vacancies)
                mins, secs = divmod(int(elapsed), 60)
                elapsed_str = f"{mins}м {secs}с" if mins else f"{secs}с"

                console.print(
                    f"  [green]✔ Завершено![/green] "
                    f"Найдено: [bold]{total}[/bold] | "
                    f"Сохранено: [green]{saved}[/green] | "
                    f"Дубли: [yellow]{skipped}[/yellow] | "
                    f"Ошибки: [red]{errors}[/red] | "
                    f"Время: [cyan]{elapsed_str}[/cyan]"
                )

                if total > 0:
                    with_salary = sum(1 for v in vacancies if v.get("salary_from") or v.get("salary_to"))
                    with_city   = sum(1 for v in vacancies if v.get("city"))
                    with_date   = sum(1 for v in vacancies if v.get("published_at"))
                    with_desc   = sum(1 for v in vacancies if v.get("description"))

                    salaries = [v["salary_from"] for v in vacancies if v.get("salary_from")]
                    dates    = [v["published_at"] for v in vacancies if v.get("published_at")]
                    companies = Counter(v.get("company") for v in vacancies if v.get("company"))

                    def _pct(n): return f"{n}/{total} ({100 * n // total}%)"

                    summary = Table(title="Сводка прогона", show_header=False, box=None, padding=(0, 2))
                    summary.add_column("", style="cyan", justify="right")
                    summary.add_column("", style="white")

                    summary.add_row("Общее время",   elapsed_str)
                    summary.add_row("С зарплатой",   _pct(with_salary))
                    summary.add_row("С городом",     _pct(with_city))
                    summary.add_row("С датой",       _pct(with_date))
                    summary.add_row("С описанием",   _pct(with_desc))

                    if salaries:
                        summary.add_row("Зарплата мин",    f"{min(salaries):,} ₽")
                        summary.add_row("Зарплата медиана", f"{sorted(salaries)[len(salaries)//2]:,} ₽")
                        summary.add_row("Зарплата макс",   f"{max(salaries):,} ₽")

                    if dates:
                        summary.add_row("Дата (старейшая)", min(dates).strftime("%d.%m.%Y"))
                        summary.add_row("Дата (свежайшая)", max(dates).strftime("%d.%m.%Y"))

                    if companies:
                        top = ", ".join(f"{c} ({n})" for c, n in companies.most_common(5))
                        summary.add_row("Топ компаний", top)

                    console.print(summary)
            except Exception as e:
                try:
                    manager.update_task_status(task.id, "failed")
                except Exception:
                    pass
                console.print(f"  [bold red]✗ Ошибка:[/bold red] {e}")


def _show_vacancy_description_command(vacancy_id: int) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        v = manager.get_vacancy(vacancy_id)
        if not v:
            console.print(f"[red]Вакансия с ID {vacancy_id} не найдена.[/red]")
            return
        if not v.description:
            console.print(f"[yellow]У вакансии #{vacancy_id} нет описания.[/yellow]")
            return
        console.print(f"\n[bold]Описание вакансии #{v.id} — {v.title or ''}[/bold]\n")
        console.print(v.description)


def _count_vacancies_command() -> None:
    with get_session() as session:
        manager = TaskManager(session)
        total = manager.count_vacancies()
        console.print(f"Всего вакансий в базе: [bold cyan]{total}[/bold cyan]")


def _parse_url_command(url: str, task_id: int = None) -> None: # Убрали source_id
    console.print(f"[yellow]Скачиваем и парсим {url}...[/yellow]")
    with get_session() as session:
        manager = TaskManager(session)
        try:
            # Передаем только url и task_id
            vacancy = manager.download_and_save_vacancy(url, task_id)
            console.print(f"[bold green]✔ Успешно сохранено![/bold green]")
            
            table = Table(show_header=False, box=None)
            table.add_column("Поле", style="cyan", justify="right")
            table.add_column("Значение", style="white")
            
            table.add_row("ID вакансии", str(vacancy.id))
            table.add_row("Task ID", str(vacancy.task_id))
            table.add_row("Должность", str(vacancy.title))
            table.add_row("Компания", str(vacancy.company))
            table.add_row("Город", str(vacancy.city)) # Теперь тут будет просто "Санкт-Петербург"
            table.add_row("З/П от", str(vacancy.salary_from))
            table.add_row("З/П до", str(vacancy.salary_to))
            table.add_row("Дата публ.", str(vacancy.published_at))
            table.add_row("URL", str(vacancy.url))
            table.add_row("Путь к HTML", str(vacancy.file_path))
            
            desc_snippet = (vacancy.description[:80] + "...") if vacancy.description else "None"
            table.add_row("Описание", desc_snippet)
            
            console.print(table)
        except Exception as e:
            console.print(f"[bold red]Ошибка при парсинге:[/bold red] {e}")


# --- CLI КОМАНДЫ (TYPER) ---

@app.command()
def init(): _init_db_command()


@app.command()
def add(
    keyword: str,
    source: str,
    city: Optional[str] = typer.Argument(None, help="Город (например: Москва)"),
): _add_task_command(keyword, source, city)


@app.command()
def run(
    task_id: Optional[int] = typer.Argument(None, help="ID задачи (без аргумента — все NEW)"),
): _run_tasks_command(task_id)


@app.command(name="tasks")
def list_tasks(limit: int = 10): _list_tasks_command(limit)


@app.command(name="status")
def set_status(task_id: int, status: str): _set_status_command(task_id, status)


@app.command(name="sources")
def list_sources(): _list_sources_command()


@app.command(name="enable-source")
def enable_source(name: str): _toggle_source_command(name, True)


@app.command(name="disable-source")
def disable_source(name: str): _toggle_source_command(name, False)


@app.command(name="vacancies")
def list_vacancies(limit: int = 10): _list_vacancies_command(limit)


@app.command(name="vacancy")
def show_vacancy(vacancy_id: int): _show_vacancy_command(vacancy_id)


@app.command(name="description")
def show_vacancy_description(vacancy_id: int): _show_vacancy_description_command(vacancy_id)


@app.command(name="count")
def count_vacancies(): _count_vacancies_command()


@app.command(name="task-vacancies")
def list_task_vacancies(task_id: int): _list_task_vacancies_command(task_id)


@app.command(name="stats")
def task_stats(task_id: int): _show_task_stats_command(task_id)


@app.command(name="logs")
def list_logs(limit: int = 20): _list_logs_command(limit)


@app.command(name="parse")
def parse_url(url: str): _parse_url_command(url)


# --- ИНТЕРАКТИВНЫЙ РЕЖИМ ---

@app.command()
def interactive():
    """Интерактивный режим работы."""
    console.print("[bold green]Job Radar Interactive Shell[/bold green]")
    console.print("[dim]Введите 'help' для списка команд. Введите 'exit' для выхода.[/dim]")

    while True:
        try:
            raw = Prompt.ask("\n[bold cyan]jh[/bold cyan] >").strip()
            if not raw: continue

            parts = shlex.split(raw)
            cmd = parts[0].lower()

            if cmd in ["exit", "quit"]: break

            if cmd == "help":
                console.print(
                    "\n[bold]Доступные команды:[/bold]\n"
                    "  [green]init[/green]                              - Создать базу данных\n"
                    "  [green]add <keyword> <source> [--city <город>][/green] - Добавить задачу (напр: add python hh --city Москва)\n"
                    "  [green]run [task_id][/green]                     - Запустить краулер (все NEW или конкретная)\n"
                    "  [green]status <id> <new_status>[/green]          - Изменить статус задачи\n"
                    "  [green]add source <name> <url>[/green]           - Добавить новый источник\n"
                    "  [green]rm task <id>[/green]                      - Удалить задачу\n"
                    "  [green]rm source <name>[/green]                  - Удалить источник\n"
                    "  [green]tasks [n][/green]                         - Показать задачи\n"
                    "  [green]sources[/green]                           - Показать источники\n"
                    "  [green]enable <source_name>[/green]              - Включить источник\n"
                    "  [green]disable <source_name>[/green]             - Отключить источник\n"
                    "  [green]vacancies [n][/green]                     - Показать вакансии\n"
                    "  [green]vacancy <id>[/green]                      - Полная информация о вакансии\n"
                    "  [green]description <id>[/green]                  - Полное описание вакансии\n"
                    "  [green]count[/green]                             - Общее число вакансий в базе\n"
                    "  [green]task-vacancies <task_id>[/green]          - Все вакансии по задаче\n"
                    "  [green]stats <task_id>[/green]                   - Статистика по задаче\n"
                    "  [green]logs [n][/green]                          - Показать логи\n"
                    "  [green]parse <url> [task_id][/green]             - Спарсить по ссылке\n"
                    "  [green]exit[/green]                              - Выход"
                )
                continue

            # === Маршрутизация команд ===

            if cmd == "init":
                _init_db_command()

            elif cmd == "add":
                if len(parts) > 1 and parts[1].lower() == "source":
                    # Формат: add source linkedin https://...
                    if len(parts) != 4:
                        console.print("[red]Использование: add source <name> <url>[/red]")
                    else:
                        _add_source_command(parts[2], parts[3])
                else:
                    # Извлекаем --city VALUE, если есть
                    city = None
                    if "--city" in parts:
                        idx = parts.index("--city")
                        if idx + 1 < len(parts):
                            city = parts[idx + 1]
                            parts = parts[:idx] + parts[idx + 2:]
                        else:
                            console.print("[red]--city требует значение, например: --city Москва[/red]")
                            continue

                    # add <keyword> <source> [--city <город>]
                    if len(parts) < 3:
                        console.print("[red]Использование: add <keyword> <source> [--city <город>][/red]")
                    elif len(parts) == 3:
                        _add_task_command(parts[1], parts[2], city)
                    else:
                        # Многословный keyword: всё кроме последнего токена = keyword, последний = source
                        kw = " ".join(parts[1:-1])
                        src = parts[-1]
                        _add_task_command(kw, src, city)

            elif cmd == "run":
                tsk_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
                _run_tasks_command(tsk_id)

            elif cmd == "status":
                if len(parts) != 3:
                    console.print("[red]Использование: status <id> <new_status>[/red]")
                else:
                    if not parts[1].isdigit():
                        console.print("[red]ID задачи должен быть числом.[/red]")
                    else:
                        _set_status_command(int(parts[1]), parts[2])

            elif cmd in ["rm", "del", "delete"]:
                if len(parts) < 3:
                    console.print("[red]Использование: rm task <id> ИЛИ rm source <name>[/red]")
                    continue

                target_type = parts[1].lower()
                target_val = parts[2]

                if target_type == "task":
                    if not target_val.isdigit():
                        console.print("[red]ID задачи должен быть числом.[/red]")
                    else:
                        _delete_task_command(int(target_val))
                elif target_type == "source":
                    _delete_source_command(target_val)
                else:
                    console.print(f"[red]Неизвестный тип объекта: {target_type}. Используйте task или source.[/red]")


            elif cmd in ["tasks", "list"]:
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                _list_tasks_command(limit)

            elif cmd == "sources":
                _list_sources_command()

            elif cmd in ["enable", "disable"]:
                if len(parts) < 2:
                    console.print(f"[red]Использование: {cmd} <source_name>[/red]")
                else:
                    _toggle_source_command(parts[1], cmd == "enable")

            elif cmd == "vacancies":
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                _list_vacancies_command(limit)

            elif cmd == "vacancy":
                if len(parts) < 2 or not parts[1].isdigit():
                    console.print("[red]Использование: vacancy <id>[/red]")
                else:
                    _show_vacancy_command(int(parts[1]))

            elif cmd == "description":
                if len(parts) < 2 or not parts[1].isdigit():
                    console.print("[red]Использование: description <id>[/red]")
                else:
                    _show_vacancy_description_command(int(parts[1]))

            elif cmd == "count":
                _count_vacancies_command()

            elif cmd == "task-vacancies":
                if len(parts) < 2 or not parts[1].isdigit():
                    console.print("[red]Использование: task-vacancies <task_id>[/red]")
                else:
                    _list_task_vacancies_command(int(parts[1]))

            elif cmd == "stats":
                if len(parts) < 2 or not parts[1].isdigit():
                    console.print("[red]Использование: stats <task_id>[/red]")
                else:
                    _show_task_stats_command(int(parts[1]))

            elif cmd == "logs":
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
                _list_logs_command(limit)

            elif cmd == "parse":
                if len(parts) < 2:
                    console.print("[red]Использование: parse <url> [task_id][/red]")
                else:
                    url = parts[1]
                    # Берем task_id, если он передан (это 3-й элемент массива parts)
                    tsk_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
                    _parse_url_command(url, tsk_id)

            else:
                console.print(f"[red]Неизвестная команда:[/red] {cmd}. Введите help.")

        except KeyboardInterrupt:
            console.print("\nType exit to quit.")
        except Exception as e:
            console.print(f"[red]Ошибка оболочки:[/red] {e}")
