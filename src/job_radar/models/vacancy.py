from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from src.job_radar.models.task import SearchTask


class Vacancy(SQLModel, table=True):
    __tablename__ = "vacancies"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="search_tasks.id")

    title: str = Field(description="Название должности")
    company: Optional[str] = Field(default=None, description="Компания")
    city: Optional[str] = Field(default=None, description="Город")
    salary_from: Optional[int] = Field(default=None)
    salary_to: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)
    url: str = Field(unique=True, description="Ссылка для дедупликации")
    published_at: Optional[datetime] = Field(default=None)

    # Связь: Много вакансий -> Одна задача
    task: "SearchTask" = Relationship(back_populates="vacancies")
