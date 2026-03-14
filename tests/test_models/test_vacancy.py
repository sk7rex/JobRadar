import pytest
from datetime import datetime
from sqlmodel import select
from src.job_radar.models.vacancy import Vacancy


def test_vacancy_creation():
    """TC-VACANCY-001: Создание вакансии с минимальными параметрами"""
    vacancy = Vacancy(
        task_id=1,
        title="Python Developer",
        url="https://example.com/vacancy/1"
    )
    
    assert vacancy.id is None
    assert vacancy.task_id == 1
    assert vacancy.title == "Python Developer"
    assert vacancy.url == "https://example.com/vacancy/1"
    assert vacancy.company is None
    assert vacancy.city is None
    assert vacancy.salary_from is None
    assert vacancy.salary_to is None
    assert vacancy.description is None
    assert vacancy.published_at is None


def test_vacancy_with_all_fields():
    """TC-VACANCY-002: Создание вакансии со всеми полями"""
    pub_date = datetime(2024, 1, 15, 10, 30)
    
    vacancy = Vacancy(
        task_id=1,
        title="Senior Python Developer",
        company="Tech Corp",
        city="Moscow",
        salary_from=300000,
        salary_to=500000,
        description="Very interesting job",
        url="https://example.com/vacancy/2",
        published_at=pub_date
    )
    
    assert vacancy.title == "Senior Python Developer"
    assert vacancy.company == "Tech Corp"
    assert vacancy.city == "Moscow"
    assert vacancy.salary_from == 300000
    assert vacancy.salary_to == 500000
    assert vacancy.description == "Very interesting job"
    assert vacancy.url == "https://example.com/vacancy/2"
    assert vacancy.published_at == pub_date


def test_vacancy_salary_range():
    """TC-VACANCY-003: Проверка различных вариантов зарплаты"""
    # Только от
    v1 = Vacancy(task_id=1, title="Job 1", url="url1", salary_from=100000)
    assert v1.salary_from == 100000
    assert v1.salary_to is None
    
    # Только до
    v2 = Vacancy(task_id=1, title="Job 2", url="url2", salary_to=200000)
    assert v2.salary_from is None
    assert v2.salary_to == 200000
    
    # Оба поля
    v3 = Vacancy(task_id=1, title="Job 3", url="url3", salary_from=100000, salary_to=200000)
    assert v3.salary_from == 100000
    assert v3.salary_to == 200000

@pytest.mark.filterwarnings("ignore:.*transaction already deassociated.*")
# т.к. когда commit() падает, связанная с ним транзакция автоматически завершается, и
# после выхода из теста фикстура session пытается выполнить rollback()
def test_vacancy_url_uniqueness(session, test_task):
    """TC-VACANCY-004: Проверка уникальности URL"""
    # Создаем первую вакансию
    v1 = Vacancy(
        task_id=test_task.id,
        title="Python Dev",
        url="https://example.com/unique"
    )
    session.add(v1)
    session.commit()
    
    # Пытаемся создать вторую с тем же URL
    v2 = Vacancy(
        task_id=test_task.id,
        title="Another Python",
        url="https://example.com/unique"  # тот же URL!
    )
    session.add(v2)
    
    # Должна быть ошибка уникальности
    with pytest.raises(Exception):
        session.commit()


def test_vacancy_task_relationship(session, test_task):
    """TC-VACANCY-005: Проверка связи вакансии с задачей"""
    # Создаем вакансию
    vacancy = Vacancy(
        task_id=test_task.id,
        title="Python Developer",
        url="https://example.com/job"
    )
    session.add(vacancy)
    session.commit()
    session.refresh(vacancy)
    
    # Проверяем связь
    assert vacancy.task is not None
    assert vacancy.task.id == test_task.id
    assert vacancy.task.keyword == test_task.keyword


def test_task_vacancies_relationship(session, test_task):
    """TC-VACANCY-006: Проверка обратной связи (задача -> вакансии)"""
    # Создаем несколько вакансий для задачи
    v1 = Vacancy(task_id=test_task.id, title="Job 1", url="url1")
    v2 = Vacancy(task_id=test_task.id, title="Job 2", url="url2")
    session.add_all([v1, v2])
    session.commit()
    
    # Обновляем задачу
    session.refresh(test_task)
    
    # Проверяем, что у задачи есть обе вакансии
    assert len(test_task.vacancies) == 2
    titles = [v.title for v in test_task.vacancies]
    assert "Job 1" in titles
    assert "Job 2" in titles


def test_vacancy_optional_fields_null(session, test_task):
    """TC-VACANCY-007: Проверка, что опциональные поля могут быть NULL"""
    vacancy = Vacancy(
        task_id=test_task.id,
        title="Python Dev",
        url="https://example.com/job",
        # все опциональные поля пропущены
    )
    session.add(vacancy)
    session.commit()
    
    # Получаем из БД
    saved = session.exec(select(Vacancy).where(Vacancy.id == vacancy.id)).first()
    
    assert saved.company is None
    assert saved.city is None
    assert saved.salary_from is None
    assert saved.salary_to is None
    assert saved.description is None
    assert saved.published_at is None