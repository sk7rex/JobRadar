from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine, Session, select

from src.job_radar.config import DATABASE_URL, DEFAULT_SOURCES
from src.job_radar.models.source import Source
from src.job_radar.models.task import SearchTask, TaskStatus

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)


def seed_sources(session: Session):
    existing_source = session.exec(select(Source)).first()
    if not existing_source:
        for src_data in DEFAULT_SOURCES:
            source = Source(**src_data)
            session.add(source)
        session.commit()

        # Создаем дефолтную задачу "manual_parsing" для источника "unknown"
        unknown_src = session.exec(select(Source).where(Source.name == "unknown")).first()
        if unknown_src:
            manual_task = SearchTask(
                source_id=unknown_src.id,
                keyword="manual_parsing",
                status=TaskStatus.COMPLETED
            )
            session.add(manual_task)
            session.commit()

        return True
    return False


def _run_migrations() -> None:
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("search_tasks")]
    if "city" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE search_tasks ADD COLUMN city VARCHAR"))
            conn.commit()


def init_db() -> str:
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if not existing_tables:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            seed_sources(session)
        return "created"

    _run_migrations()
    return "exists"


def get_session():
    return Session(engine)
