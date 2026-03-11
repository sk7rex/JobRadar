from datetime import datetime
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

# Импорты только для проверки типов, чтобы избежать циклической зависимости
if TYPE_CHECKING:
    from src.job_radar.models.source import Source
    from src.job_radar.models.vacancy import Vacancy
    from src.job_radar.models.log import Log


class TaskStatus(str, Enum):
    """
    Статусы задачи на поиск вакансий.
     - NEW: только создана, еще не обработана краулером
     - IN_PROGRESS: краулер взял в работу, идет сбор данных
     - COMPLETED: краулер завершил сбор успешно, данные готовы
     - FAILED: краулер завершил с ошибкой, данные не готовы
     - CANCELLED: задача отменена пользователем, не обрабатывается краулером
     - EXPIRED: задача устарела, не обрабатывается краулером
     - RETRIED: задача была повторно запущена после неудачной попытки
    """
    NEW = "new"  # Только создана
    IN_PROGRESS = "in_progress"  # В работе (краулер взял)
    COMPLETED = "completed"  # Завершена успешно
    FAILED = "failed"  # Ошибка при сборе
    CANCELLED = "cancelled"  # Отменена пользователем
    EXPIRED = "expired"  # Устарела
    RETRIED = "retried"  # Повторно запущена


class SearchTask(SQLModel, table=True):
    __tablename__ = "search_tasks"

    id: Optional[int] = Field(default=None, primary_key=True, description="Уникальный идентификатор задачи")

    # Внешний ключ на таблицу Sources
    source_id: int = Field(foreign_key="sources.id", description="Ссылка на источник")

    keyword: str = Field(index=True, description="Ключевое слово поиска")
    status: TaskStatus = Field(default=TaskStatus.NEW, description="Текущий статус")
    items_found: int = Field(default=0, description="Количество найденных вакансий")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Связи (ORM)
    source_relation: "Source" = Relationship(back_populates="tasks")
    vacancies: List["Vacancy"] = Relationship(back_populates="task")
    logs: List["Log"] = Relationship(back_populates="task")
