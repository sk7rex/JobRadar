import shlex

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.job_hunter.database import init_db, get_session
from src.job_hunter.models.task import TaskStatus
from src.job_hunter.services.manager import TaskManager

app = typer.Typer(help="Job Hunter Manager CLI")
console = Console()


def _init_db_command() -> None:
    """Внутренняя функция инициализации БД."""
    try:
        status = init_db()

        if status == "created":
            console.print("[bold green]✔ База данных успешно инициализирована![/bold green]")
        elif status == "exists":
            console.print("[bold yellow]⚠ База данных уже инициализирована[/bold yellow]")

    except Exception as e:
        console.print(f"[bold red]✘ Ошибка инициализации:[/bold red] {e}")


def _add_task_command(keyword: str, source: str) -> None:
    """Внутренняя функция добавления задачи."""
    with get_session() as session:
        manager = TaskManager(session)
        try:
            task = manager.create_task(keyword, source)
            console.print(
                f"[green]✔ Задача создана![/green] "
                f"ID: [bold]{task.id}[/bold] | "
                f"Ищем: [magenta]{task.keyword}[/magenta] @ [blue]{task.source}[/blue]"
            )
        except ValueError as e:
            console.print(f"[bold red]Ошибка валидации:[/bold red] {e}")
        except Exception as e:
            console.print(f"[bold red]Неожиданная ошибка:[/bold red] {e}")


def _list_tasks_command(limit: int = 10) -> None:
    """Внутренняя функция отображения списка задач."""
    with get_session() as session:
        manager = TaskManager(session)
        tasks = manager.list_tasks(limit)

        if not tasks:
            console.print("[yellow]Очередь задач пуста.[/yellow]")
            return

        table = Table(title="Очередь задач Job Hunter")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Запрос", style="magenta")
        table.add_column("Источник", style="blue")
        table.add_column("Статус", justify="center")
        table.add_column("Создано", style="dim")

        for task in tasks:
            status_color = "white"
            if task.status == TaskStatus.NEW:
                status_color = "yellow"
            elif task.status == TaskStatus.IN_PROGRESS:
                status_color = "blue"
            elif task.status == TaskStatus.COMPLETED:
                status_color = "green"
            elif task.status == TaskStatus.FAILED:
                status_color = "red"

            table.add_row(
                str(task.id),
                task.keyword,
                task.source,
                f"[{status_color}]{task.status.value}[/{status_color}]",
                task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )

        console.print(table)


@app.command()
def init() -> None:
    """Инициализация базы данных (создание таблиц)."""
    _init_db_command()


@app.command()
def add(keyword: str, source: str) -> None:
    """Добавить новую задачу. Пример: add 'python developer' habr"""
    _add_task_command(keyword, source)


@app.command(name="list")
def list_tasks(limit: int = 10) -> None:
    """Показать список последних задач."""
    _list_tasks_command(limit)


@app.command()
def interactive() -> None:
    """Запуск интерактивного режима (мини-интерпретатор команд)."""
    console.print("[bold green]Добро пожаловать в Job Hunter interactive shell![/bold green]")
    console.print("[dim]Доступные команды:[/dim]")
    console.print("  [cyan]init[/cyan]")
    console.print("  [cyan]add <keyword> <source>[/cyan]")
    console.print("  [cyan]list [limit][/cyan]")
    console.print("  [cyan]help[/cyan]")
    console.print("  [cyan]exit[/cyan] или [cyan]quit[/cyan]")

    while True:
        try:
            raw_command = Prompt.ask("\n[bold cyan]jh[/bold cyan] >").strip()

            if not raw_command:
                continue

            # shlex.split нужен, чтобы корректно разбирать строки с кавычками:
            # add "python developer" habr
            parts = shlex.split(raw_command)

            if not parts:
                continue

            command = parts[0].lower()

            if command in {"exit", "quit"}:
                console.print("[bold green]Выход из interactive shell.[/bold green]")
                break

            if command == "help":
                console.print("[dim]Доступные команды:[/dim]")
                console.print("  [cyan]init[/cyan]")
                console.print("  [cyan]add <keyword> <source>[/cyan]")
                console.print("  [cyan]list [limit][/cyan]")
                console.print("  [cyan]help[/cyan]")
                console.print("  [cyan]exit[/cyan] или [cyan]quit[/cyan]")
                continue

            if command == "init":
                if len(parts) != 1:
                    console.print("[red]Команда init не принимает аргументы.[/red]")
                    continue
                _init_db_command()
                continue

            if command == "add":
                if len(parts) < 3:
                    console.print("[red]Использование: add <keyword> <source>[/red]")
                    console.print('[dim]Пример: add "python developer" habr[/dim]')
                    continue

                keyword = " ".join(parts[1:-1])
                source = parts[-1]
                _add_task_command(keyword, source)
                continue

            if command == "list":
                if len(parts) == 1:
                    _list_tasks_command()
                    continue

                if len(parts) == 2:
                    try:
                        limit = int(parts[1])
                    except ValueError:
                        console.print("[red]Параметр limit должен быть целым числом.[/red]")
                        continue

                    _list_tasks_command(limit)
                    continue

                console.print("[red]Использование: list [limit][/red]")
                continue

            console.print(f"[red]Неизвестная команда:[/red] {command}")
            console.print("[dim]Введите 'help', чтобы увидеть список команд.[/dim]")

        except KeyboardInterrupt:
            console.print("\n[bold yellow]Прервано пользователем. Для выхода введите exit.[/bold yellow]")
        except Exception as e:
            console.print(f"[bold red]Ошибка:[/bold red] {e}")
