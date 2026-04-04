import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import Dict, Any

def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text

def parse_hh_vacancy(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, 'html.parser')
    
    title_tag = soup.find('h1', {'data-qa': 'vacancy-title'})
    title = title_tag.text.strip() if title_tag else None

    company_tag = soup.find('a', {'data-qa': 'vacancy-company-name'}) or soup.find('span', {'data-qa': 'vacancy-company-name'})
    company = company_tag.text.replace('\xa0', ' ').strip() if company_tag else None

    city_tag = soup.find('p', {'data-qa': 'vacancy-view-location'}) or soup.find('span', {'data-qa': 'vacancy-view-raw-address'})
    if city_tag:
        # Разбиваем по запятой и берем только первый элемент (Город)
        city = city_tag.text.split(',')[0].strip()
    else:
        city = None

    desc_tag = soup.find('div', {'data-qa': 'vacancy-description'})
    description = desc_tag.get_text(separator='\n').strip() if desc_tag else None

    published_at = None
    meta_date = soup.find('meta', itemprop='datePosted')
    if meta_date and meta_date.get('content'):
        try:
            published_at = datetime.strptime(meta_date['content'], '%Y-%m-%d')
        except ValueError:
            pass

    salary_from = None
    salary_to = None
    salary_tag = soup.find('div', {'data-qa': 'vacancy-salary'})
    
    if salary_tag:
        salary_text = salary_tag.text.replace('\u202f', '').replace(' ', '').lower()
        numbers = [int(n) for n in re.findall(r'\d+', salary_text)]
        
        if "от" in salary_text and "до" in salary_text and len(numbers) >= 2:
            salary_from, salary_to = numbers[0], numbers[1]
        elif "от" in salary_text and len(numbers) >= 1:
            salary_from = numbers[0]
        elif "до" in salary_text and len(numbers) >= 1:
            salary_to = numbers[0]
        elif len(numbers) >= 2:
            salary_from, salary_to = numbers[0], numbers[1]
        elif len(numbers) == 1:
            salary_from = salary_to = numbers[0]

    return {
        "title": title,
        "company": company,
        "city": city,
        "description": description,
        "salary_from": salary_from,
        "salary_to": salary_to,
        "published_at": published_at
    }