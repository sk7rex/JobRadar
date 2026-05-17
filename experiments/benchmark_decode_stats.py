#!/usr/bin/env python
"""
Многократное измерение времени загрузки gamma/delta индексов.
Вычисляет среднее, медиану, стандартное отклонение.
Запуск: poetry run python experiments/benchmark_decode_stats.py [--iterations N]
"""

import time
import struct
import statistics
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_radar.config import INDEX_DIR
from src.job_radar.services.index.inverted_index import InvertedIndex
from src.job_radar.services.index import codec_bitarray


def load_original(variant: str):
    """Оригинальный кодек (через InvertedIndex.load_*)"""
    idx = InvertedIndex()
    start = time.perf_counter()
    if variant == "gamma":
        idx.load_gamma(INDEX_DIR / "index_gamma.bin")
    else:
        idx.load_delta(INDEX_DIR / "index_delta.bin")
    elapsed = time.perf_counter() - start
    return elapsed, len(idx.dictionary)


def load_bitarray(variant: str):
    """Кодек на bitarray (прямое декодирование)"""
    start = time.perf_counter()
    dictionary = {}
    filename = INDEX_DIR / f"index_{variant}.bin"
    with open(filename, "rb") as f:
        while True:
            len_byte = f.read(1)
            if not len_byte:
                break
            token_len = len_byte[0]
            token_bytes = f.read(token_len)
            if len(token_bytes) < token_len:
                break
            token = token_bytes.decode('utf-8')
            count_data = f.read(4)
            if len(count_data) < 4:
                break
            count = struct.unpack('>I', count_data)[0]
            encoded_len_data = f.read(4)
            if len(encoded_len_data) < 4:
                break
            encoded_len = struct.unpack('>I', encoded_len_data)[0]
            encoded_data = f.read(encoded_len)
            if len(encoded_data) < encoded_len:
                break
            if variant == "gamma":
                ids = codec_bitarray.decode_deltas_gamma(encoded_data)
            else:
                ids = codec_bitarray.decode_deltas_delta(encoded_data)
            dictionary[token] = ids
    elapsed = time.perf_counter() - start
    return elapsed, len(dictionary)


def run_benchmark(variant: str, loader_func, iterations: int = 10):
    """Запускает loader_func несколько раз и возвращает статистику"""
    times = []
    token_counts = []
    # Прогрев (один прогон, не в статистику)
    _, _ = loader_func(variant)
    for i in range(iterations):
        t, cnt = loader_func(variant)
        times.append(t)
        token_counts.append(cnt)
        # небольшая пауза, чтобы не нагружать диск (опционально)
        time.sleep(0.1)
    mean = statistics.mean(times)
    median = statistics.median(times)
    stdev = statistics.stdev(times) if len(times) > 1 else 0.0
    return {
        "times": times,
        "mean": mean,
        "median": median,
        "stdev": stdev,
        "min": min(times),
        "max": max(times),
        "tokens": token_counts[0] if token_counts else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=10, help="Количество замеров (по умолчанию 10)")
    args = parser.parse_args()
    iters = args.iterations

    print(f"Статистическое сравнение загрузки индексов (iterations={iters})\n")
    results = {}

    for variant in ["gamma", "delta"]:
        print(f"\n=== {variant.upper()} индекс ===")
        for name, loader in [("Оригинал (codec.py)", load_original),
                              ("Bitarray (codec_bitarray.py)", load_bitarray)]:
            stats = run_benchmark(variant, loader, iters)
            results[(variant, name)] = stats
            print(f"{name}:")
            print(f"  Среднее: {stats['mean']:.3f} с ± {stats['stdev']:.3f} с")
            print(f"  Медиана: {stats['median']:.3f} с")
            print(f"  Мин/Макс: {stats['min']:.3f} / {stats['max']:.3f} с")
            print(f"  Токенов: {stats['tokens']}")

    # Сводная таблица ускорения (bitarray vs оригинал)
    print("\n" + "="*60)
    print("Сводка ускорения (bitarray / оригинал):")
    for variant in ["gamma", "delta"]:
        orig_mean = results[(variant, "Оригинал (codec.py)")]["mean"]
        ba_mean = results[(variant, "Bitarray (codec_bitarray.py)")]["mean"]
        speedup = orig_mean / ba_mean
        print(f"{variant.upper()}: {speedup:.2f}x (исходный {orig_mean:.3f} с -> bitarray {ba_mean:.3f} с)")

    # Сравнение gamma vs delta внутри одного кодера
    print("\n" + "="*60)
    print("Сравнение gamma vs delta (внутри одного кодера):")
    for name in ["Оригинал (codec.py)", "Bitarray (codec_bitarray.py)"]:
        g_mean = results[("gamma", name)]["mean"]
        d_mean = results[("delta", name)]["mean"]
        diff = d_mean - g_mean
        print(f"{name}: gamma {g_mean:.3f} с, delta {d_mean:.3f} с, разница {diff:+.3f} с ({diff/g_mean*100:+.1f}%)")


if __name__ == "__main__":
    main()