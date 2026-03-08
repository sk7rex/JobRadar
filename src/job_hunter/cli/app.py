import typer
from rich.console import Console
from rich.table import Table

from src.job_hunter.database import init_db, get_session
from src.job_hunter.services.manager import TaskManager
from src.job_hunter.models.task import TaskStatus

app = typer.Typer(help="Job Hunter Manager CLI")
console = Console()


@app.command()
def init():
    """Инициализация базы данных (создание таблиц)."""
    try:
        init_db()
        console.print("[bold green]✔ База данных успешно инициализирована![/bold green]")
    except Exception as e:
        console.print(f"[bold red]✘ Ошибка:[/bold red] {e}")


@app.command()
def add(keyword: str, source: str):
    """Добавить новую задачу (пример: add 'python' 'habr')."""
    with get_session() as session:
        manager = TaskManager(session)
        try:
            task = manager.create_task(keyword, source)
            console.print(
                f"[green]Задача создана![/green] ID: [bold]{task.id}[/bold] | Ищем: {task.keyword} @ {task.source}")
        except ValueError as e:
            console.print(f"[bold red]Ошибка валидации:[/bold red] {e}")


@app.command()
def list(limit: int = 10):
    """Показать список последних задач."""
    with get_session() as session:
        manager = TaskManager(session)
        tasks = manager.list_tasks(limit)

        if not tasks:
            console.print("[yellow]Очередь задач пуста.[/yellow]")
            return

        # Рисуем красивую таблицу
        table = Table(title="Очередь задач Job Hunter")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Запрос", style="magenta")
        table.add_column("Источник", style="blue")
        table.add_column("Статус", justify="center")
        table.add_column("Создано", style="dim")

        for t in tasks:
            # Цвет статуса
            status_color = "white"
            if t.status == TaskStatus.NEW:
                status_color = "yellow"
            elif t.status == TaskStatus.IN_PROGRESS:
                status_color = "blue"
            elif t.status == TaskStatus.COMPLETED:
                status_color = "green"
            elif t.status == TaskStatus.FAILED:
                status_color = "red"

            table.add_row(
                str(t.id),
                t.keyword,
                t.source,
                f"[{status_color}]{t.status.value}[/{status_color}]",
                t.created_at.strftime("%H:%M %d.%m")
            )

        console.print(table)