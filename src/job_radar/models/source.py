from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from src.job_radar.models.task import SearchTask

class Source(SQLModel, table=True):
    __tablename__ = "sources"

    id: Optional[int] = Field(default=None, primary_key=True, description="Уникальный идентификатор источника")
    name: str = Field(unique=True, index=True, description="Короткое имя источника: habr, hh")
    url: str = Field(description="Базовый URL сайта")
    is_active: bool = Field(default=True, description="Флаг: используется ли источник")

    # Связь: Один источник -> Много задач
    tasks: List["SearchTask"] = Relationship(back_populates="source_relation")