from sqlmodel import select, Session
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.config import ALLOWED_SOURCES


class TaskManager:
    def __init__(self, session: Session):
        self.session = session

    def create_task(self, keyword: str, source: str) -> SearchTask:
        """
        Создает новую задачу.
        Выбрасывает ValueError, если источник некорректен или задача уже существует.
        """
        # 1. Нормализация данных (приводим к нижнему регистру)
        clean_kw = keyword.strip().lower()
        clean_src = source.strip().lower()

        # 2. Валидация источника
        if clean_src not in ALLOWED_SOURCES:
            raise ValueError(f"Источник '{source}' недоступен. Разрешены: {', '.join(ALLOWED_SOURCES)}")

        # 3. Проверка на дубликаты (Идемпотентность)
        # Ищем такую же задачу, которая еще не завершена
        existing = self.session.exec(
            select(SearchTask).where(
                SearchTask.keyword == clean_kw,
                SearchTask.source == clean_src,
                SearchTask.status.in_([TaskStatus.NEW, TaskStatus.IN_PROGRESS])
            )
        ).first()

        if existing:
            raise ValueError(f"Такая задача уже в работе (ID: {existing.id}, Статус: {existing.status})")

        # 4. Сохранение
        task = SearchTask(keyword=clean_kw, source=clean_src)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)

        return task

    def list_tasks(self, limit: int = 10):
        """Возвращает список последних задач."""
        query = select(SearchTask).order_by(SearchTask.created_at.desc()).limit(limit)
        return self.session.exec(query).all()