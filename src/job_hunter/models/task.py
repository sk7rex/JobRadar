from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


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
    """
    Модель данных для задачи на поиск вакансий.

    Каждая запись — это задача поиска вакансий
    по конкретному ключевому слову и источнику.
    """

    # Уникальный идентификатор задачи
    id: Optional[int] = Field(default=None, primary_key=True)

    # Входные параметры
    keyword: str = Field(index=True,
                         description="Ключевое слово поиска (Python, Java)")
    source: str = Field(description="Источник (habr, hh)")

    # Состояние
    status: TaskStatus = Field(default=TaskStatus.NEW)
    items_found: int = Field(default=0, description="Сколько вакансий нашли")

    # Временные метки
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
