"""
TC-CODEC-001..040  Побитовые кодеки (pure Python): codec.py
"""

import pytest
from src.job_radar.services.index.codec import (
    BitWriter, BitReader,
    gamma_encode, gamma_decode,
    delta_encode, delta_decode,
    encode_deltas_gamma, decode_deltas_gamma,
    encode_deltas_delta, decode_deltas_delta,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _write_flush(bits):
    w = BitWriter()
    for b in bits:
        w.write_bit(b)
    return w.flush()


def _gamma_roundtrip(n: int) -> int:
    data = _write_flush(gamma_encode(n))
    return gamma_decode(BitReader(data))


def _delta_roundtrip(n: int) -> int:
    data = _write_flush(delta_encode(n))
    return delta_decode(BitReader(data))


# ─────────────────────────────────────────────────────────────
# TC-CODEC-001..007  BitWriter / BitReader
# ─────────────────────────────────────────────────────────────

class TestBitIO:

    def test_write_read_bit_one(self):
        """TC-CODEC-001"""
        w = BitWriter()
        w.write_bit(1)
        assert BitReader(w.flush()).read_bit() == 1

    def test_write_read_bit_zero(self):
        """TC-CODEC-002"""
        w = BitWriter()
        w.write_bit(0)
        assert BitReader(w.flush()).read_bit() == 0

    def test_write_8_bits_exact_byte(self):
        """TC-CODEC-003: 10110101 == 0xb5"""
        w = BitWriter()
        w.write_bits(0b10110101, 8)
        assert w.flush() == b'\xb5'

    def test_flush_pads_incomplete_byte_with_zeros(self):
        """TC-CODEC-004: 3 бита 101 → 0b10100000"""
        w = BitWriter()
        w.write_bits(0b101, 3)
        assert w.flush() == b'\xa0'

    def test_read_bits_as_number(self):
        """TC-CODEC-005"""
        w = BitWriter()
        w.write_bits(0b110, 3)
        assert BitReader(w.flush()).read_bits(3) == 6

    def test_read_bit_empty_data_raises_eof(self):
        """TC-CODEC-006"""
        with pytest.raises(EOFError):
            BitReader(b'').read_bit()

    def test_16_bit_symmetry(self):
        """TC-CODEC-007"""
        bits = [1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 1]
        r = BitReader(_write_flush(bits))
        assert [r.read_bit() for _ in range(16)] == bits


# ─────────────────────────────────────────────────────────────
# TC-CODEC-010..017  Гамма-код Элиаса
# ─────────────────────────────────────────────────────────────

class TestGammaCodec:

    def test_gamma_encode_1(self):
        """TC-CODEC-010"""
        assert list(gamma_encode(1)) == [1]

    def test_gamma_encode_2(self):
        """TC-CODEC-011"""
        assert list(gamma_encode(2)) == [0, 1, 0]

    def test_gamma_encode_3(self):
        """TC-CODEC-012"""
        assert list(gamma_encode(3)) == [0, 1, 1]

    def test_gamma_encode_4(self):
        """TC-CODEC-013"""
        assert list(gamma_encode(4)) == [0, 0, 1, 0, 0]

    @pytest.mark.parametrize("n", range(1, 101))
    def test_gamma_roundtrip(self, n):
        """TC-CODEC-014"""
        assert _gamma_roundtrip(n) == n

    def test_gamma_encode_zero_raises(self):
        """TC-CODEC-015"""
        with pytest.raises(ValueError):
            list(gamma_encode(0))

    def test_gamma_encode_negative_raises(self):
        """TC-CODEC-016"""
        with pytest.raises(ValueError):
            list(gamma_encode(-1))

    def test_gamma_encode_large_value(self):
        """TC-CODEC-017"""
        assert _gamma_roundtrip(1000) == 1000


# ─────────────────────────────────────────────────────────────
# TC-CODEC-020..024  Дельта-код Элиаса
# ─────────────────────────────────────────────────────────────

class TestDeltaCodec:

    def test_delta_encode_1_equals_gamma_encode_1(self):
        """TC-CODEC-020"""
        assert list(delta_encode(1)) == list(gamma_encode(1))

    @pytest.mark.parametrize("n", range(1, 101))
    def test_delta_roundtrip(self, n):
        """TC-CODEC-021"""
        assert _delta_roundtrip(n) == n

    def test_delta_encode_zero_raises(self):
        """TC-CODEC-022"""
        with pytest.raises(ValueError):
            list(delta_encode(0))

    def test_delta_encode_large_value(self):
        """TC-CODEC-023"""
        assert _delta_roundtrip(65536) == 65536

    def test_delta_more_efficient_than_gamma_for_large_n(self):
        """TC-CODEC-024: для n=128 дельта использует меньше бит, чем гамма"""
        gamma_bits = list(gamma_encode(128))
        delta_bits = list(delta_encode(128))
        assert len(delta_bits) <= len(gamma_bits)


# ─────────────────────────────────────────────────────────────
# TC-CODEC-030..040  Posting-листы
# ─────────────────────────────────────────────────────────────

class TestPostingLists:

    def test_encode_gamma_empty_list(self):
        """TC-CODEC-030"""
        assert encode_deltas_gamma([]) == b''

    def test_decode_gamma_empty_bytes(self):
        """TC-CODEC-031"""
        assert decode_deltas_gamma(b'') == []

    def test_gamma_single_element_roundtrip(self):
        """TC-CODEC-032"""
        assert decode_deltas_gamma(encode_deltas_gamma([42])) == [42]

    def test_gamma_multiple_elements_roundtrip(self):
        """TC-CODEC-033"""
        ids = [1, 3, 7, 15, 31]
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ids

    def test_delta_single_element_roundtrip(self):
        """TC-CODEC-034"""
        assert decode_deltas_delta(encode_deltas_delta([100])) == [100]

    def test_delta_multiple_elements_roundtrip(self):
        """TC-CODEC-035"""
        ids = [1, 3, 7, 15, 31]
        assert decode_deltas_delta(encode_deltas_delta(ids)) == ids

    def test_gamma_large_list_roundtrip(self):
        """TC-CODEC-036"""
        ids = list(range(1, 1001))
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ids

    def test_gamma_consecutive_ids_roundtrip(self):
        """TC-CODEC-037"""
        ids = list(range(1, 51))
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ids

    def test_gamma_large_deltas_roundtrip(self):
        """TC-CODEC-038"""
        ids = [1, 1000, 100_000]
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ids

    def test_gamma_codec_matches_bitarray_implementation(self):
        """TC-CODEC-039"""
        from src.job_radar.services.index.codec_bitarray import (
            encode_deltas_gamma as ba_enc,
            decode_deltas_gamma as ba_dec,
        )
        ids = [5, 10, 20, 50, 200]
        assert decode_deltas_gamma(encode_deltas_gamma(ids)) == ba_dec(ba_enc(ids))

    def test_delta_codec_matches_bitarray_implementation(self):
        """TC-CODEC-040"""
        from src.job_radar.services.index.codec_bitarray import (
            encode_deltas_delta as ba_enc,
            decode_deltas_delta as ba_dec,
        )
        ids = [5, 10, 20, 50, 200]
        assert decode_deltas_delta(encode_deltas_delta(ids)) == ba_dec(ba_enc(ids))
