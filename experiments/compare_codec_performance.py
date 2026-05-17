#!/usr/bin/env python
"""
Сравнение производительности декодирования gamma и delta индексов:
- чистая реализация (codec.py)
- реализация на bitarray (codec_bitarray.py)
"""
import time
import struct
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.job_radar.config import INDEX_DIR
from src.job_radar.services.index.inverted_index import InvertedIndex
from src.job_radar.services.index import codec_bitarray


def load_original(variant: str):
    """Загружает индекс через родной codec (встроенный в InvertedIndex)."""
    idx = InvertedIndex()
    start = time.perf_counter()
    if variant == "gamma":
        idx.load_gamma(INDEX_DIR / "index_gamma.bin")
    else:
        idx.load_delta(INDEX_DIR / "index_delta.bin")
    elapsed = time.perf_counter() - start
    return elapsed, len(idx.dictionary)


def load_bitarray(variant: str):
    """Загружает индекс через bitarray, напрямую декодируя файл."""
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
            # выбираем нужную функцию декодирования
            if variant == "gamma":
                ids = codec_bitarray.decode_deltas_gamma(encoded_data)
            else:
                ids = codec_bitarray.decode_deltas_delta(encoded_data)
            dictionary[token] = ids
    elapsed = time.perf_counter() - start
    return elapsed, len(dictionary)


def main():
    for variant in ["gamma", "delta"]:
        print(f"\n=== Сравнение для {variant.upper()} индекса ===\n")
        # Оригинал
        t_orig, cnt_orig = load_original(variant)
        print(f"Оригинальный codec (чистый Python): {t_orig:.3f} с, токенов: {cnt_orig}")
        # Bitarray
        t_ba, cnt_ba = load_bitarray(variant)
        print(f"Codec на bitarray: {t_ba:.3f} с, токенов: {cnt_ba}")
        print(f"Ускорение: {t_orig / t_ba:.2f}x")
        print(f"Совместимость (токены): {'ДА' if cnt_orig == cnt_ba else 'НЕТ'}")


if __name__ == "__main__":
    main()