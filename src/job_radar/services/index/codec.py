"""
Элиас-кодирование (гамма и дельта) с побитовым вводом/выводом.
Все числа положительные целые (>=1). Порядок битов: big-endian внутри байта.
"""

from typing import Iterator, List


class BitWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.accumulator = 0
        self.bits_left = 8

    def write_bit(self, bit: int):
        self.accumulator = (self.accumulator << 1) | (bit & 1)
        self.bits_left -= 1
        if self.bits_left == 0:
            self.buffer.append(self.accumulator)
            self.accumulator = 0
            self.bits_left = 8

    def write_bits(self, value: int, count: int):
        for i in range(count - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def flush(self) -> bytes:
        while self.bits_left != 8:
            self.write_bit(0)
        return bytes(self.buffer)


class BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.bit_pos = 0
        self.current_byte = self.data[0] if data else 0

    def read_bit(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError("End of bitstream")
        bit = (self.current_byte >> (7 - self.bit_pos)) & 1
        self.bit_pos += 1
        if self.bit_pos == 8:
            self.pos += 1
            if self.pos < len(self.data):
                self.current_byte = self.data[self.pos]
            self.bit_pos = 0
        return bit

    def read_bits(self, count: int) -> int:
        value = 0
        for _ in range(count):
            value = (value << 1) | self.read_bit()
        return value


# ---- Гамма-код ----
def gamma_encode(n: int) -> Iterator[int]:
    if n < 1:
        raise ValueError("Gamma encoding works only for n>=1")
    k = n.bit_length() - 1
    for _ in range(k):
        yield 0
    yield 1
    if k > 0:
        for i in range(k - 1, -1, -1):
            yield (n >> i) & 1


def gamma_decode(reader: BitReader) -> int:
    zeros = 0
    while reader.read_bit() == 0:
        zeros += 1
    if zeros == 0:
        return 1
    rest = reader.read_bits(zeros)
    return (1 << zeros) | rest


# ---- Дельта-код ----
def delta_encode(n: int) -> Iterator[int]:
    if n < 1:
        raise ValueError("Delta encoding works only for n>=1")
    k = n.bit_length()
    yield from gamma_encode(k)
    if k > 1:
        rest = n & ((1 << (k - 1)) - 1)
        for i in range(k - 2, -1, -1):
            yield (rest >> i) & 1


def delta_decode(reader: BitReader) -> int:
    k = gamma_decode(reader)
    if k == 1:
        return 1
    rest = reader.read_bits(k - 1)
    return (1 << (k - 1)) | rest


# ---- Кодирование списков дельт (posting lists) ----
def encode_deltas_gamma(ids: List[int]) -> bytes:
    if not ids:
        return b''
    w = BitWriter()
    prev = ids[0]
    for bit in gamma_encode(prev):
        w.write_bit(bit)
    for cur in ids[1:]:
        delta = cur - prev
        for bit in gamma_encode(delta):
            w.write_bit(bit)
        prev = cur
    return w.flush()


def decode_deltas_gamma(data: bytes) -> List[int]:
    if not data:
        return []
    r = BitReader(data)
    res = []
    first = gamma_decode(r)
    res.append(first)
    prev = first
    while r.pos < len(r.data) or r.bit_pos != 0:
        try:
            delta = gamma_decode(r)
            cur = prev + delta
            res.append(cur)
            prev = cur
        except EOFError:
            break
    return res


def encode_deltas_delta(ids: List[int]) -> bytes:
    if not ids:
        return b''
    w = BitWriter()
    prev = ids[0]
    for bit in delta_encode(prev):
        w.write_bit(bit)
    for cur in ids[1:]:
        delta = cur - prev
        for bit in delta_encode(delta):
            w.write_bit(bit)
        prev = cur
    return w.flush()


def decode_deltas_delta(data: bytes) -> List[int]:
    if not data:
        return []
    r = BitReader(data)
    first = delta_decode(r)
    res = [first]
    prev = first
    while r.pos < len(r.data) or r.bit_pos != 0:
        try:
            delta = delta_decode(r)
            cur = prev + delta
            res.append(cur)
            prev = cur
        except EOFError:
            break
    return res