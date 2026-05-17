import json
import gzip
import struct
import re
from pathlib import Path
from typing import List, Dict, Set, Optional

from src.job_radar.config import INDEX_DIR

from src.job_radar.services.index.codec_bitarray import (
    encode_deltas_gamma, decode_deltas_gamma,
    encode_deltas_delta, decode_deltas_delta,
)


class InvertedIndex:
    def __init__(self):
        self.dictionary: Dict[str, List[int]] = {}

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        if not text:
            return set()
        text = text.lower()
        text = re.sub(r'[^a-zа-яё0-9]', ' ', text)
        tokens = text.split()
        return {t for t in tokens if len(t) >= 2}

    def build(self, vacancies: List[dict]) -> None:
        self.dictionary.clear()
        for vac in vacancies:
            doc_id = vac['id']
            title = vac.get('title', '') or ''
            desc = vac.get('description', '') or ''
            full_text = f"{title} {desc}"
            tokens = self._tokenize(full_text)
            for token in tokens:
                if token not in self.dictionary:
                    self.dictionary[token] = []
                self.dictionary[token].append(doc_id)
        for token in self.dictionary:
            self.dictionary[token].sort()

    # ---------- Plain JSON ----------
    def save_plain(self, path: Path) -> int:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.dictionary, f, ensure_ascii=False, separators=(',', ':'))
        return path.stat().st_size

    def load_plain(self, path: Path) -> None:
        with open(path, 'r', encoding='utf-8') as f:
            self.dictionary = json.load(f)

    # ---------- Gzip (альтернативное сжатие) ----------
    def save_gzip(self, path: Path) -> int:
        with gzip.open(path, 'wt', encoding='utf-8') as f:
            json.dump(self.dictionary, f)
        return path.stat().st_size

    def load_gzip(self, path: Path) -> None:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            self.dictionary = json.load(f)

    # ---------- Gamma ----------
    def save_gamma(self, path: Path) -> int:
        with open(path, 'wb') as f:
            for token, ids in self.dictionary.items():
                token_bytes = token.encode('utf-8')
                if len(token_bytes) > 255:
                    raise ValueError(f"Token too long: {token}")
                f.write(bytes([len(token_bytes)]))
                f.write(token_bytes)
                f.write(struct.pack('>I', len(ids)))
                encoded = encode_deltas_gamma(ids)
                f.write(struct.pack('>I', len(encoded)))
                f.write(encoded)
        return path.stat().st_size

    def load_gamma(self, path: Path) -> None:
        self.dictionary.clear()
        with open(path, 'rb') as f:
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
                ids = decode_deltas_gamma(encoded_data)
                self.dictionary[token] = ids

    # ---------- Delta ----------
    def save_delta(self, path: Path) -> int:
        with open(path, 'wb') as f:
            for token, ids in self.dictionary.items():
                token_bytes = token.encode('utf-8')
                if len(token_bytes) > 255:
                    raise ValueError(f"Token too long: {token}")
                f.write(bytes([len(token_bytes)]))
                f.write(token_bytes)
                f.write(struct.pack('>I', len(ids)))
                encoded = encode_deltas_delta(ids)
                f.write(struct.pack('>I', len(encoded)))
                f.write(encoded)
        return path.stat().st_size

    def load_delta(self, path: Path) -> None:
        self.dictionary.clear()
        with open(path, 'rb') as f:
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
                ids = decode_deltas_delta(encoded_data)
                self.dictionary[token] = ids

    # ---------- Поиск ----------
    def search(self, query: str, mode: str = "or") -> List[int]:
        tokens = self._tokenize(query)
        if not tokens:
            return []
        lists = [self.dictionary.get(tok, []) for tok in tokens]
        if not lists:
            return []
        if mode == "or":
            result = set()
            for lst in lists:
                result.update(lst)
            return sorted(result)
        elif mode == "and":
            if not lists:
                return []
            shortest = min(lists, key=len)
            result = []
            for doc in shortest:
                if all(doc in lst for lst in lists):
                    result.append(doc)
            return result
        else:
            raise ValueError(f"Unknown mode: {mode}")