from datetime import datetime
from typing import List
from typing import Optional

from sqlalchemy.orm import selectinload
from sqlmodel import select, Session

from src.job_radar.config import HTML_STORAGE_DIR
from src.job_radar.models.log import Log
from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus
from src.job_radar.models.vacancy import Vacancy
from src.job_radar.services.parser import fetch_html, parse_hh_vacancy


class TaskManager:
    VALID_TRANSITIONS = {
        TaskStatus.NEW: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.EXPIRED},
        TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
        TaskStatus.FAILED: {TaskStatus.RETRIED, TaskStatus.CANCELLED},
        TaskStatus.RETRIED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
        TaskStatus.CANCELLED: {TaskStatus.RETRIED},
        TaskStatus.COMPLETED: set(),  # Пустое множество -> терминальное состояние
        TaskStatus.EXPIRED: set(),    # Пустое множество -> терминальное состояние
    }

    def __init__(self, session: Session):
        self.session = session

    # --- ЗАДАЧИ (TASKS) ---

    def create_task(self, keyword: str, source_name: str) -> SearchTask:
        clean_kw = keyword.strip().lower()
        clean_src_name = source_name.strip().lower()

        if not clean_kw:
            raise ValueError("Ключевое слово не может быть пустым")

        source = self.session.exec(
            select(Source).where(Source.name == clean_src_name)
        ).first()

        if not source:
            all_sources = self.session.exec(select(Source.name)).all()
            raise ValueError(f"Источник '{source_name}' не найден. Доступны: {', '.join(all_sources)}")

        if not source.is_active:
            raise ValueError(f"Источник '{source_name}' временно отключен администратором.")

        existing = self.session.exec(
            select(SearchTask).where(
                SearchTask.keyword == clean_kw,
                SearchTask.source_id == source.id,
                SearchTask.status.in_([TaskStatus.NEW, TaskStatus.IN_PROGRESS])
            )
        ).first()

        if existing:
            raise ValueError(f"Такая задача уже в работе (ID: {existing.id}, Статус: {existing.status})")

        task = SearchTask(keyword=clean_kw, source_id=source.id)
        self.session.add(task)
        self.session.flush()

        log = Log(
            task_id=task.id,
            level="INFO",
            message=f"Task created via CLI. Keyword: {clean_kw}, Source: {clean_src_name}"
        )
        self.session.add(log)

        self.session.commit()
        self.session.refresh(task)
        self.session.refresh(task, ["source_relation"])

        return task

    def update_task_status(self, task_id: int, new_status: str) -> SearchTask:
        """
        Изменяет статус задачи с проверкой конечного автомата (FSM).
        """
        task = self.session.get(SearchTask, task_id)
        if not task:
            raise ValueError(f"Задача с ID {task_id} не найдена.")

        # Пытаемся преобразовать входную строку в Enum
        try:
            status_enum = TaskStatus(new_status.lower())
        except ValueError:
            valid_statuses = ", ".join([s.value for s in TaskStatus])
            raise ValueError(f"Неверный статус '{new_status}'. Доступные: {valid_statuses}")

        old_status = task.status
        if old_status == status_enum:
            return task  # Статус не изменился (ничего не делаем)

        # === ПРОВЕРКА КОНЕЧНОГО АВТОМАТА (FSM) ===
        allowed_next_states = self.VALID_TRANSITIONS.get(old_status, set())
        
        if status_enum not in allowed_next_states:
            # Формируем красивую строку с доступными статусами для вывода ошибки
            if allowed_next_states:
                allowed_str = ", ".join([s.value for s in allowed_next_states])
                error_msg = f"Нельзя перевести из '{old_status.value}' в '{status_enum.value}'. Разрешены только: {allowed_str}"
            else:
                error_msg = f"Задача в статусе '{old_status.value}' завершена (терминальное состояние), статус менять нельзя."
            
            raise ValueError(error_msg)

        # Если проверка пройдена, меняем статус
        task.status = status_enum
        task.updated_at = datetime.now()

        # Логируем успешное изменение
        log = Log(
            task_id=task.id,
            level="INFO",
            message=f"Status changed FSM: {old_status.value} -> {status_enum.value}"
        )
        self.session.add(log)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)

        return task

    def list_tasks(self, limit: int = 10) -> List[SearchTask]:
        query = (
            select(SearchTask)
            .options(selectinload(SearchTask.source_relation))
            .order_by(SearchTask.created_at.desc())
            .limit(limit)
        )
        return self.session.exec(query).all()

    def delete_task(self, task_id: int) -> bool:
        task = self.session.get(SearchTask, task_id)
        if not task:
            return False

        logs = self.session.exec(select(Log).where(Log.task_id == task_id)).all()
        for log in logs:
            self.session.delete(log)

        vacancies = self.session.exec(select(Vacancy).where(Vacancy.task_id == task_id)).all()
        for v in vacancies:
            self.session.delete(v)

        self.session.delete(task)
        self.session.commit()
        return True

    # --- ИСТОЧНИКИ (SOURCES) ---

    def list_sources(self) -> List[Source]:
        return self.session.exec(select(Source)).all()

    def add_source(self, name: str, url: str) -> Source:
        clean_name = name.strip().lower()
        existing = self.session.exec(select(Source).where(Source.name == clean_name)).first()
        if existing:
            raise ValueError(f"Источник '{clean_name}' уже существует.")

        source = Source(name=clean_name, url=url, is_active=True)
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def delete_source(self, name: str) -> bool:
        clean_name = name.strip().lower()
        source = self.session.exec(select(Source).where(Source.name == clean_name)).first()

        if not source:
            raise ValueError(f"Источник '{clean_name}' не найден.")

        tasks = self.session.exec(select(SearchTask).where(SearchTask.source_id == source.id)).first()
        if tasks:
            raise ValueError(
                f"Нельзя удалить источник '{clean_name}', так как к нему привязаны задачи. Сначала удалите задачи.")

        self.session.delete(source)
        self.session.commit()
        return True

    # --- ДРУГОЕ ---

    def list_vacancies(self, limit: int = 10) -> List[Vacancy]:
        query = (
            select(Vacancy)
            .options(selectinload(Vacancy.task))
            .order_by(Vacancy.id.desc())
            .limit(limit)
        )
        return self.session.exec(query).all()

    def list_logs(self, limit: int = 20) -> List[Log]:
        query = (
            select(Log)
            .order_by(Log.created_at.desc())
            .limit(limit)
        )
        return self.session.exec(query).all()

    def download_and_save_vacancy(self, url: str, task_id: Optional[int] = None) -> Vacancy:
        existing_vacancy = self.session.exec(select(Vacancy).where(Vacancy.url == url)).first()
        if existing_vacancy:
            raise ValueError(f"Вакансия {url} уже есть в БД (ID: {existing_vacancy.id}).")

        # Определяем, к какой задаче привязать
        if task_id:
            # Проверяем, существует ли переданная задача
            t = self.session.get(SearchTask, task_id)
            if not t: 
                raise ValueError(f"Задача с ID {task_id} не найдена.")
            actual_task_id = task_id
        else:
            # Ничего не передали -> берем дефолтную 'unknown -> manual_parsing'
            manual_task = self.session.exec(select(SearchTask).where(SearchTask.keyword == "manual_parsing")).first()
            if not manual_task:
                raise ValueError("Сделайте init. Нет базовой задачи для ручного парсинга.")
            actual_task_id = manual_task.id

        # Парсим
        html_content = fetch_html(url)
        parsed_data = parse_hh_vacancy(html_content)

        # Сохраняем в БД
        vacancy = Vacancy(
            task_id=actual_task_id,
            url=url,
            title=parsed_data["title"] or "No Title",
            company=parsed_data["company"],
            city=parsed_data["city"],
            description=parsed_data["description"],
            salary_from=parsed_data["salary_from"],
            salary_to=parsed_data["salary_to"],
            published_at=parsed_data["published_at"]
        )
        self.session.add(vacancy)
        self.session.commit()
        self.session.refresh(vacancy)

        # Сохраняем HTML локально
        file_name = f"vacancy_{vacancy.id}.html"
        file_path = HTML_STORAGE_DIR / file_name
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        vacancy.file_path = str(file_path)
        
        log = Log(task_id=actual_task_id, level="INFO", message=f"Saved vacancy {vacancy.id} locally")
        self.session.add(log)
        
        self.session.add(vacancy)
        self.session.commit()
        self.session.refresh(vacancy)

        return vacancy