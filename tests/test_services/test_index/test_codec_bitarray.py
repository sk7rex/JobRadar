"""
Кодеки на основе библиотеки bitarray: codec_bitarray.py
"""

import pytest
from bitarray import bitarray
from src.job_radar.services.index.codec_bitarray import (
    gamma_encode, gamma_decode,
    delta_encode, delta_decode,
    encode_deltas_gamma, decode_deltas_gamma,
    encode_deltas_delta, decode_deltas_delta,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _gamma_roundtrip(n: int) -> int:
    ba = gamma_encode(n)
    val, _ = gamma_decode(ba, 0)
    return val


def _delta_roundtrip(n: int) -> int:
    ba = delta_encode(n)
    val, _ = delta_decode(ba, 0)
    return val


# ─────────────────────────────────────────────────────────────
# Гамма-код
# ─────────────────────────────────────────────────────────────

class TestGammaCodecBitarray:

    def test_gamma_encode_returns_bitarray(self):
        assert isinstance(gamma_encode(1), bitarray)

    def test_gamma_encode_1(self):
        assert list(gamma_encode(1)) == [1]

    def test_gamma_encode_2(self):
        assert list(gamma_encode(2)) == [0, 1, 0]

    def test_gamma_encode_3(self):
        assert list(gamma_encode(3)) == [0, 1, 1]

    def test_gamma_encode_4(self):
        assert list(gamma_encode(4)) == [0, 0, 1, 0, 0]

    @pytest.mark.parametrize("n", range(1, 101))
    def test_gamma_roundtrip(self, n):
        assert _gamma_roundtrip(n) == n

    def test_gamma_encode_zero_raises(self):
        with pytest.raises(ValueError):
            gamma_encode(0)

    def test_gamma_encode_negative_raises(self):
        with pytest.raises(ValueError):
            gamma_encode(-1)

    def test_gamma_encode_large_value(self):
        assert _gamma_roundtrip(1000) == 1000

    def test_gamma_decode_returns_updated_position(self):
        """Позиция после декодирования == длине закодированной последовательности."""
        ba = gamma_encode(5)
        val, pos = gamma_decode(ba, 0)
        assert val == 5
        assert pos == len(ba)

    def test_gamma_decode_mid_stream(self):
        """Декодирование с ненулевой стартовой позицией."""
        prefix = gamma_encode(3)
        payload = gamma_encode(7)
        combined = prefix + payload
        _, start = gamma_decode(combined, 0)
        val, _ = gamma_decode(combined, start)
        assert val == 7


# ─────────────────────────────────────────────────────────────
# Дельта-код
# ─────────────────────────────────────────────────────────────

class TestDeltaCodecBitarray:

    def test_delta_encode_returns_bitarray(self):
        assert isinstance(delta_encode(1), bitarray)

    def test_delta_encode_1_matches_gamma(self):
        assert list(delta_encode(1)) == list(gamma_encode(1))

    @pytest.mark.parametrize("n", range(1, 101))
    def test_delta_roundtrip(self, n):
        assert _delta_roundtrip(n) == n

    def test_delta_encode_zero_raises(self):
        with pytest.raises(ValueError):
            delta_encode(0)

    def test_delta_encode_negative_raises(self):
        with pytest.raises(ValueError):
            delta_encode(-1)

    def test_delta_encode_large_value(self):
        assert _delta_roundtrip(65536) == 65536

    def test_delta_decode_returns_updated_position(self):
        ba = delta_encode(10)
        val, pos = delta_decode(ba, 0)
        assert val == 10
        assert pos == len(ba)


# ─────────────────────────────────────────────────────────────
# Posting-листы
# ─────────────────────────────────────────────────────────────

class TestPostingListsBitarray:

    def test_encode_gamma_empty(self):
        assert encode_deltas_gamma([]) == b''

    def test_decode_gamma_empty(self):
        assert decode_deltas_gamma(b'') == []

    def test_encode_delta_empty(self):
        assert encode_deltas_delta([]) == b''

    def test_decode_delta_empty(self):
        assert decode_deltas_delta(b'') == []

    def test_gamma_roundtrip(self):
        ids = [1, 3, 7, 15, 31, 100]
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ids

    def test_delta_roundtrip(self):
        ids = [1, 3, 7, 15, 31, 100]
        assert decode_deltas_delta(encode_deltas_delta(ids)) == ids

    def test_gamma_large_list(self):
        ids = list(range(1, 501))
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ids

    def test_delta_large_list(self):
        ids = list(range(1, 501))
        assert decode_deltas_delta(encode_deltas_delta(ids)) == ids

    def test_gamma_single_element(self):
        assert decode_deltas_gamma(encode_deltas_gamma([999])) == [999]

    def test_delta_single_element(self):
        assert decode_deltas_delta(encode_deltas_delta([999])) == [999]
