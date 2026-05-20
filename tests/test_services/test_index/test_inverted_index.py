"""
TC-IDX-001..068  Класс InvertedIndex: построение, сериализация, поиск.
"""

import pytest
from src.job_radar.services.index.inverted_index import InvertedIndex


# ─────────────────────────────────────────────────────────────
# Фикстуры
# ─────────────────────────────────────────────────────────────

SAMPLE_VACANCIES = [
    {"id": 1, "title": "Python разработчик",     "description": "Django REST Flask"},
    {"id": 2, "title": "Java Backend Developer",  "description": "Spring Kafka Python"},
    {"id": 3, "title": "Frontend React разработчик", "description": "JavaScript TypeScript"},
    {"id": 4, "title": "DevOps инженер",          "description": "Kubernetes Docker Python"},
]


@pytest.fixture
def built_index():
    idx = InvertedIndex()
    idx.build(SAMPLE_VACANCIES)
    return idx


@pytest.fixture
def compression_index():
    """50 вакансий с повторяющимися токенами — posting-листы длинные, сжатие гарантировано."""
    vacancies = [
        {
            "id": i,
            "title": "Python разработчик backend senior",
            "description": "Django REST API Python разработчик",
        }
        for i in range(1, 51)
    ]
    idx = InvertedIndex()
    idx.build(vacancies)
    return idx


# ─────────────────────────────────────────────────────────────
# TC-IDX-001..010  Построение индекса
# ─────────────────────────────────────────────────────────────

class TestIndexBuild:

    def test_empty_input_gives_empty_dictionary(self):
        """TC-IDX-001"""
        idx = InvertedIndex()
        idx.build([])
        assert idx.dictionary == {}

    def test_tokens_extracted_from_title(self):
        """TC-IDX-002"""
        idx = InvertedIndex()
        idx.build([{"id": 1, "title": "Python разработчик", "description": ""}])
        assert "python" in idx.dictionary
        assert "разработчик" in idx.dictionary
        assert idx.dictionary["python"] == [1]

    def test_tokens_extracted_from_description(self):
        """TC-IDX-003"""
        idx = InvertedIndex()
        idx.build([{"id": 1, "title": "", "description": "Backend Python"}])
        assert "backend" in idx.dictionary
        assert "python" in idx.dictionary
        assert idx.dictionary["python"] == [1]

    def test_common_token_indexes_both_docs(self):
        """TC-IDX-004"""
        idx = InvertedIndex()
        idx.build([
            {"id": 1, "title": "Python", "description": ""},
            {"id": 2, "title": "Python Java", "description": ""},
        ])
        assert idx.dictionary["python"] == [1, 2]

    def test_posting_lists_are_sorted(self):
        """TC-IDX-005"""
        idx = InvertedIndex()
        idx.build([
            {"id": 10, "title": "Python", "description": ""},
            {"id": 2,  "title": "Python", "description": ""},
            {"id": 5,  "title": "Python", "description": ""},
        ])
        lst = idx.dictionary["python"]
        assert lst == sorted(lst)

    def test_tokens_lowercased(self):
        """TC-IDX-006"""
        idx = InvertedIndex()
        idx.build([
            {"id": 1, "title": "PYTHON", "description": ""},
            {"id": 2, "title": "python", "description": ""},
        ])
        assert sorted(idx.dictionary["python"]) == [1, 2]

    def test_single_char_tokens_filtered(self):
        """TC-IDX-007: токены короче 2 символов отбрасываются"""
        idx = InvertedIndex()
        idx.build([{"id": 1, "title": "я в IT", "description": ""}])
        assert "я" not in idx.dictionary
        assert "в" not in idx.dictionary

    def test_special_chars_stripped(self):
        """TC-IDX-008: C++ → "++" не попадает в индекс"""
        idx = InvertedIndex()
        idx.build([{"id": 1, "title": "C++ разработчик", "description": ""}])
        assert "++" not in idx.dictionary
        assert "разработчик" in idx.dictionary

    def test_none_fields_do_not_raise(self):
        """TC-IDX-009"""
        idx = InvertedIndex()
        idx.build([{"id": 1, "title": None, "description": None}])
        assert isinstance(idx.dictionary, dict)

    def test_rebuild_clears_old_dictionary(self):
        """TC-IDX-010"""
        idx = InvertedIndex()
        idx.build([{"id": 1, "title": "Python", "description": ""}])
        assert "python" in idx.dictionary

        idx.build([{"id": 2, "title": "Java", "description": ""}])
        assert "python" not in idx.dictionary
        assert "java" in idx.dictionary


# ─────────────────────────────────────────────────────────────
# TC-IDX-020..023  Сериализация — Plain JSON
# ─────────────────────────────────────────────────────────────

class TestPlainSerialization:

    def test_save_plain_creates_file(self, built_index, tmp_path):
        """TC-IDX-020"""
        path = tmp_path / "index.json"
        size = built_index.save_plain(path)
        assert path.exists()
        assert size > 0

    def test_load_plain_restores_dictionary(self, built_index, tmp_path):
        """TC-IDX-021"""
        path = tmp_path / "index.json"
        built_index.save_plain(path)

        idx2 = InvertedIndex()
        idx2.load_plain(path)
        assert idx2.dictionary == built_index.dictionary

    def test_save_plain_returns_actual_file_size(self, built_index, tmp_path):
        """TC-IDX-022"""
        path = tmp_path / "index.json"
        size = built_index.save_plain(path)
        assert size == path.stat().st_size

    def test_empty_index_plain_roundtrip(self, tmp_path):
        """TC-IDX-023"""
        idx = InvertedIndex()
        idx.build([])
        path = tmp_path / "empty.json"
        idx.save_plain(path)

        idx2 = InvertedIndex()
        idx2.load_plain(path)
        assert idx2.dictionary == {}


# ─────────────────────────────────────────────────────────────
# TC-IDX-030..034  Сериализация — Gamma
# ─────────────────────────────────────────────────────────────

class TestGammaSerialization:

    def test_save_gamma_creates_file(self, built_index, tmp_path):
        """TC-IDX-030"""
        path = tmp_path / "index_gamma.bin"
        size = built_index.save_gamma(path)
        assert path.exists()
        assert size > 0

    def test_load_gamma_restores_dictionary(self, built_index, tmp_path):
        """TC-IDX-031"""
        path = tmp_path / "index_gamma.bin"
        built_index.save_gamma(path)

        idx2 = InvertedIndex()
        idx2.load_gamma(path)
        assert idx2.dictionary == built_index.dictionary

    def test_gamma_smaller_than_plain_on_large_corpus(self, compression_index, tmp_path):
        """TC-IDX-032: бинарный файл меньше JSON при достаточном объёме данных"""
        plain_size = compression_index.save_plain(tmp_path / "index.json")
        gamma_size = compression_index.save_gamma(tmp_path / "index_gamma.bin")
        assert gamma_size < plain_size

    def test_empty_index_gamma_roundtrip(self, tmp_path):
        """TC-IDX-033"""
        idx = InvertedIndex()
        idx.build([])
        path = tmp_path / "empty.bin"
        idx.save_gamma(path)

        idx2 = InvertedIndex()
        idx2.load_gamma(path)
        assert idx2.dictionary == {}

    def test_long_token_raises_value_error(self, tmp_path):
        """TC-IDX-034: токен длиннее 255 байт (UTF-8) вызывает ValueError"""
        idx = InvertedIndex()
        idx.dictionary["а" * 128] = [1]  # 128 × 2 байта = 256 байт UTF-8
        with pytest.raises(ValueError, match="Token too long"):
            idx.save_gamma(tmp_path / "err.bin")


# ─────────────────────────────────────────────────────────────
# TC-IDX-040..043  Сериализация — Delta
# ─────────────────────────────────────────────────────────────

class TestDeltaSerialization:

    def test_save_delta_creates_file(self, built_index, tmp_path):
        """TC-IDX-040"""
        path = tmp_path / "index_delta.bin"
        size = built_index.save_delta(path)
        assert path.exists()
        assert size > 0

    def test_load_delta_restores_dictionary(self, built_index, tmp_path):
        """TC-IDX-041"""
        path = tmp_path / "index_delta.bin"
        built_index.save_delta(path)

        idx2 = InvertedIndex()
        idx2.load_delta(path)
        assert idx2.dictionary == built_index.dictionary

    def test_delta_smaller_than_plain_on_large_corpus(self, compression_index, tmp_path):
        """TC-IDX-042"""
        plain_size = compression_index.save_plain(tmp_path / "index.json")
        delta_size = compression_index.save_delta(tmp_path / "index_delta.bin")
        assert delta_size < plain_size

    def test_empty_index_delta_roundtrip(self, tmp_path):
        """TC-IDX-043"""
        idx = InvertedIndex()
        idx.build([])
        path = tmp_path / "empty.bin"
        idx.save_delta(path)

        idx2 = InvertedIndex()
        idx2.load_delta(path)
        assert idx2.dictionary == {}


# ─────────────────────────────────────────────────────────────
# TC-IDX-050..051  Согласованность форматов
# ─────────────────────────────────────────────────────────────

class TestFormatConsistency:

    def test_all_formats_produce_same_dictionary(self, built_index, tmp_path):
        """TC-IDX-050"""
        built_index.save_plain(tmp_path / "index.json")
        built_index.save_gamma(tmp_path / "index_gamma.bin")
        built_index.save_delta(tmp_path / "index_delta.bin")

        idx_plain = InvertedIndex()
        idx_plain.load_plain(tmp_path / "index.json")

        idx_gamma = InvertedIndex()
        idx_gamma.load_gamma(tmp_path / "index_gamma.bin")

        idx_delta = InvertedIndex()
        idx_delta.load_delta(tmp_path / "index_delta.bin")

        assert idx_plain.dictionary == idx_gamma.dictionary
        assert idx_plain.dictionary == idx_delta.dictionary

    def test_search_results_identical_across_formats(self, built_index, tmp_path):
        """TC-IDX-051"""
        built_index.save_plain(tmp_path / "index.json")
        built_index.save_gamma(tmp_path / "index_gamma.bin")
        built_index.save_delta(tmp_path / "index_delta.bin")

        def load_search(load_fn, path, query):
            idx = InvertedIndex()
            load_fn(idx, path)
            return idx.search(query)

        query = "python"
        res_plain = load_search(lambda i, p: i.load_plain(p),  tmp_path / "index.json",       query)
        res_gamma = load_search(lambda i, p: i.load_gamma(p),  tmp_path / "index_gamma.bin",  query)
        res_delta = load_search(lambda i, p: i.load_delta(p),  tmp_path / "index_delta.bin",  query)

        assert res_plain == res_gamma
        assert res_plain == res_delta


# ─────────────────────────────────────────────────────────────
# TC-IDX-060..068  Поиск
# ─────────────────────────────────────────────────────────────

class TestSearch:

    def test_empty_query_returns_empty(self, built_index):
        """TC-IDX-060"""
        assert built_index.search("") == []

    def test_unknown_token_returns_empty(self, built_index):
        """TC-IDX-061"""
        assert built_index.search("несуществующийтокен12345") == []

    def test_single_token_found(self, built_index):
        """TC-IDX-062"""
        result = built_index.search("python")
        assert len(result) > 0
        assert all(isinstance(doc_id, int) for doc_id in result)

    def test_or_search_is_union(self, built_index):
        """TC-IDX-063"""
        # python: docs 1,2,4  |  java: doc 2  → union: 1,2,4
        python_ids = set(built_index.search("python", mode="or"))
        java_ids   = set(built_index.search("java",   mode="or"))
        combined   = set(built_index.search("python java", mode="or"))
        assert combined == python_ids | java_ids

    def test_and_search_is_intersection(self, built_index):
        """TC-IDX-064: только doc 2 содержит и 'java' и 'python'"""
        result = built_index.search("java python", mode="and")
        assert result == [2]

    def test_and_search_empty_when_no_intersection(self, built_index):
        """TC-IDX-065: 'react' в doc 3, 'kafka' в doc 2 — пересечения нет"""
        result = built_index.search("react kafka", mode="and")
        assert result == []

    def test_search_result_is_sorted(self, built_index):
        """TC-IDX-066"""
        result = built_index.search("python разработчик", mode="or")
        assert result == sorted(result)

    def test_unknown_mode_raises_value_error(self, built_index):
        """TC-IDX-067"""
        with pytest.raises(ValueError, match="Unknown mode"):
            built_index.search("python", mode="xor")

    def test_search_is_case_insensitive(self, built_index):
        """TC-IDX-068"""
        assert built_index.search("python") == built_index.search("PYTHON")
