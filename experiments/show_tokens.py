#!/usr/bin/env python
"""
Скрипт для просмотра токенов инвертированного индекса.
Запуск: python -m experiments.show_tokens
"""

from src.job_radar.config import INDEX_DIR
from src.job_radar.services.index.inverted_index import InvertedIndex

def main():
    # Загружаем plain-индекс (можно заменить на delta/gamma)
    idx = InvertedIndex()
    plain_path = INDEX_DIR / "index_plain.json"
    if not plain_path.exists():
        print(f"Индекс не найден: {plain_path}. Сначала выполните index-build.")
        return
    idx.load_plain(plain_path)
    
    print(f"Всего токенов в словаре: {len(idx.dictionary)}")
    
    # 1. Первые 50 токенов (по алфавиту)
    print("\n--- Первые 50 токенов (по алфавиту) ---")
    for i, token in enumerate(sorted(idx.dictionary.keys())[:50]):
        print(f"{i+1:3}. {token} -> {len(idx.dictionary[token])} документов")
    
    # 2. Топ-50 самых частых токенов
    sorted_by_freq = sorted(idx.dictionary.items(), key=lambda x: len(x[1]), reverse=True)
    print("\n--- Топ-50 самых частых токенов ---")
    for i, (token, postings) in enumerate(sorted_by_freq[:50]):
        print(f"{i+1:3}. {token} -> {len(postings)} документов")
    
    # 3. Токены, встречающиеся ровно в 1 документе
    unique_tokens = [t for t, p in idx.dictionary.items() if len(p) == 1]
    print(f"\nТокенов, встречающихся в 1 документе: {len(unique_tokens)} ({100*len(unique_tokens)/len(idx.dictionary):.1f}%)")
    
    # 4. Информация по конкретному токену (например, "python")
    token_ex = "python"
    if token_ex in idx.dictionary:
        ids = idx.dictionary[token_ex]
        print(f"\nТокен '{token_ex}': {len(ids)} вакансий, первые ID: {ids[:20]}")
    else:
        print(f"\nТокен '{token_ex}' не найден.")

if __name__ == "__main__":
    main()