from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from src.job_radar.models.task import SearchTask

class Log(SQLModel, table=True):
    __tablename__ = "logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="search_tasks.id")
    
    level: str = Field(default="INFO", description="INFO, WARNING, ERROR")
    message: str = Field(description="Текст сообщения")
    created_at: datetime = Field(default_factory=datetime.now)

    # Связь: Много логов -> Одна задача
    task: "SearchTask" = Relationship(back_populates="logs")