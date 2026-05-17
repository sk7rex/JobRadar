#!/usr/bin/env python
import time
from pathlib import Path
from sqlmodel import select

from src.job_radar.database import get_session
from src.job_radar.models.vacancy import Vacancy
from src.job_radar.config import INDEX_DIR
from src.job_radar.services.index.inverted_index import InvertedIndex


def main():
    print("Загрузка вакансий из БД...")
    with get_session() as session:
        vacancies = session.exec(select(Vacancy)).all()
        vac_list = [
            {"id": v.id, "title": v.title or "", "description": v.description or ""}
            for v in vacancies
        ]
    print(f"Документов в корпусе: {len(vac_list)}")

    # Строим индекс один раз
    idx = InvertedIndex()
    build_start = time.perf_counter()
    idx.build(vac_list)
    build_time = time.perf_counter() - build_start
    print(f"Токенов в словаре: {len(idx.dictionary)}")
    print(f"Время построения словаря: {build_time:.2f} с\n")

    # Сохраняем три варианта и замеряем время сохранения
    sizes = {}
    save_times = {}
    for name, method in [("plain", idx.save_plain), ("delta", idx.save_delta), ("gamma", idx.save_gamma)]:
        path = INDEX_DIR / f"index_{name}.bin" if name != "plain" else INDEX_DIR / f"index_{name}.json"
        start = time.perf_counter()
        size = method(path)
        save_time = time.perf_counter() - start
        sizes[name] = size
        save_times[name] = save_time
        print(f"{name}: размер {size/1024/1024:.2f} МБ, сохранение {save_time:.2f} с")

    # Загружаем каждый вариант и ищем
    query = "python разработчик"
    print(f"\nПоисковый запрос: '{query}'")
    results = {}
    for variant in ["plain", "delta", "gamma"]:
        idx_load = InvertedIndex()
        load_start = time.perf_counter()
        if variant == "plain":
            idx_load.load_plain(INDEX_DIR / "index_plain.json")
        elif variant == "delta":
            idx_load.load_delta(INDEX_DIR / "index_delta.bin")
        else:
            idx_load.load_gamma(INDEX_DIR / "index_gamma.bin")
        load_time = time.perf_counter() - load_start

        search_start = time.perf_counter()
        docs = idx_load.search(query, mode="or")
        search_time = time.perf_counter() - search_start

        results[variant] = {
            "docs": len(docs),
            "load_time": load_time,
            "search_time": search_time * 1000,
        }

    # --- Таблица в точности как в ТЗ ---
    plain_mb = sizes["plain"] / 1024 / 1024
    delta_mb = sizes["delta"] / 1024 / 1024
    gamma_mb = sizes["gamma"] / 1024 / 1024

    delta_compress = (1 - delta_mb / plain_mb) * 100
    gamma_compress = (1 - gamma_mb / plain_mb) * 100

    # Время построения: для plain = build_time, для delta/gamma = build_time + сохранение
    build_plain = build_time
    build_delta = build_time + save_times["delta"]
    build_gamma = build_time + save_times["gamma"]

    print("\n┌─────────────────┬──────────┬──────────┬──────────────┬──────────────┐")
    print("│                 │ Несжатый │  Дельта  │    Гамма     │              │")
    print("├─────────────────┼──────────┼──────────┼──────────────┼──────────────┤")
    print(f"│ Размер файла    │ {plain_mb:6.2f} МБ │ {delta_mb:6.2f} МБ │ {gamma_mb:6.2f} МБ │              │")
    print(f"│ Сжатие (%)      │    —     │ {delta_compress:6.2f}%  │ {gamma_compress:6.2f}%  │              │")
    print(f"│ Время построен. │ {build_plain:6.2f} с │ {build_delta:6.2f} с │ {build_gamma:6.2f} с │              │")
    print(f"│ Время загрузки  │ {results['plain']['load_time']:6.2f} с │ {results['delta']['load_time']:6.2f} с │ {results['gamma']['load_time']:6.2f} с │              │")
    print(f"│ Время поиска    │ {results['plain']['search_time']:6.2f} мс │ {results['delta']['search_time']:6.2f} мс │ {results['gamma']['search_time']:6.2f} мс │              │")
    print(f"│ Найдено (docs)  │ {results['plain']['docs']:6d}    │ {results['delta']['docs']:6d}    │ {results['gamma']['docs']:6d}    │ ← должно = │")
    print("└─────────────────┴──────────┴──────────┴──────────────┴──────────────┘")


if __name__ == "__main__":
    main()