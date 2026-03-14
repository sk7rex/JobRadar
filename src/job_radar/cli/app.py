import shlex

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


def _add_task_command(keyword: str, source: str) -> None:
    with get_session() as session:
        manager = TaskManager(session)
        try:
            task = manager.create_task(keyword, source)
            src_name = task.source_relation.name if task.source_relation else source
            console.print(
                f"[green][OK] Задача создана![/green] "
                f"ID: [bold]{task.id}[/bold] | "
                f"Ищем: [magenta]{task.keyword}[/magenta] @ [blue]{src_name}[/blue]"
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


# --- CLI КОМАНДЫ (TYPER) ---

@app.command()
def init(): _init_db_command()


@app.command()
def add(keyword: str, source: str): _add_task_command(keyword, source)


@app.command(name="tasks")
def list_tasks(limit: int = 10): _list_tasks_command(limit)


@app.command(name="status")
def set_status(task_id: int, status: str): _set_status_command(task_id, status)


@app.command(name="sources")
def list_sources(): _list_sources_command()


@app.command(name="vacancies")
def list_vacancies(limit: int = 10): _list_vacancies_command(limit)


@app.command(name="logs")
def list_logs(limit: int = 20): _list_logs_command(limit)


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
                    "  [green]init[/green]                         - Создать базу данных\n"
                    "  [green]add <keyword> <source>[/green]               - Добавить задачу (напр: add python hh)\n"
                    "  [green]status <id> <new_status>[/green]            - Изменить статус задачи\n"
                    "  [green]add source <name> <url>[/green]      - Добавить новый источник\n"
                    "  [green]rm task <id>[/green]                 - Удалить задачу\n"
                    "  [green]rm source <name>[/green]             - Удалить источник\n"
                    "  [green]tasks [n][/green]                    - Показать задачи (n=кол-во)\n"
                    "  [green]sources[/green]                      - Показать источники\n"
                    "  [green]vacancies [n][/green]                - Показать вакансии\n"
                    "  [green]logs [n][/green]                     - Показать логи\n"
                    "  [green]exit[/green]                         - Выход"
                )
                continue

            # === Маршрутизация команд ===

            if cmd == "init":
                _init_db_command()

            elif cmd == "add":
                # Проверяем, добавляем ли мы источник или задачу
                if len(parts) > 1 and parts[1].lower() == "source":
                    # Формат: add source linkedin https://...
                    if len(parts) != 4:
                        console.print("[red]Использование: add source <name> <url>[/red]")
                    else:
                        _add_source_command(parts[2], parts[3])
                else:
                    # Обычная задача: add python hh
                    if len(parts) < 3:
                        console.print("[red]Использование: add <keyword> <source>[/red]")
                    else:
                        # Собираем keyword, если он из нескольких слов, а source последнее
                        if len(parts) == 3:
                            kw, src = parts[1], parts[2]
                        else:
                            kw, src = " ".join(parts[1:-1]), parts[-1]
                        _add_task_command(kw, src)

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

            elif cmd == "vacancies":
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                _list_vacancies_command(limit)

            elif cmd == "logs":
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
                _list_logs_command(limit)

            else:
                console.print(f"[red]Неизвестная команда:[/red] {cmd}. Введите help.")

        except KeyboardInterrupt:
            console.print("\nType exit to quit.")
        except Exception as e:
            console.print(f"[red]Ошибка оболочки:[/red] {e}")
