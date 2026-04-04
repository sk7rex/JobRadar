# ===== FILE: services/parser.py =====
# PATH: ./job_radar/services/parser.py

import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, Any

def fetch_html(url: str) -> str:
    """Скачивает HTML страницу по ссылке."""
    # HeadHunter очень не любит ботов, поэтому нужно притвориться браузером
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()  # Проверка на ошибки (404, 500 и т.д.)
    return response.text

def parse_hh_vacancy(html: str) -> Dict[str, Any]:
    """Парсит HTML страницу вакансии HeadHunter и возвращает словарь с данными."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Извлекаем заголовок (название вакансии)
    title_tag = soup.find('h1', {'data-qa': 'vacancy-title'})
    title = title_tag.text.strip() if title_tag else "Неизвестная должность"

    # Извлекаем компанию
    company_tag = soup.find('a', {'data-qa': 'vacancy-company-name'})
    company = company_tag.text.strip() if company_tag else None

    # Извлекаем город
    city_tag = soup.find('p', {'data-qa': 'vacancy-view-location'})
    if not city_tag:
        city_tag = soup.find('span', {'data-qa': 'vacancy-view-raw-address'})
    city = city_tag.text.strip() if city_tag else None

    # Извлекаем описание
    desc_tag = soup.find('div', {'data-qa': 'vacancy-description'})
    description = desc_tag.text.strip() if desc_tag else None

    # Парсинг зарплаты (упрощенный вариант, так как там часто пишут "от X до Y руб.")
    salary_from = None
    salary_to = None
    salary_tag = soup.find('div', {'data-qa': 'vacancy-salary'})
    
    if salary_tag:
        salary_text = salary_tag.text.replace('\u202f', '').replace(' ', '') # убираем пробелы
        # Ищем числа с помощью регулярных выражений
        numbers = re.findall(r'\d+', salary_text)
        if len(numbers) >= 1:
            salary_from = int(numbers[0])
        if len(numbers) >= 2:
            salary_to = int(numbers[1])

    return {
        "title": title,
        "company": company,
        "city": city,
        "description": description,
        "salary_from": salary_from,
        "salary_to": salary_to
    }