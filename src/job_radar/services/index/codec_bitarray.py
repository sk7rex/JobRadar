from typing import List
from bitarray import bitarray


def gamma_encode(n: int) -> bitarray:
    if n < 1:
        raise ValueError("n must be >=1")
    k = n.bit_length() - 1
    ba = bitarray()
    ba.extend([0] * k)
    ba.append(1)
    if k:
        rest = n & ((1 << k) - 1)
        bits = bin(rest)[2:].zfill(k)
        ba.extend([int(b) for b in bits])
    return ba


def gamma_decode(ba: bitarray, pos: int) -> tuple[int, int]:
    zeros = 0
    # Считаем нули до первой единицы или до конца
    while pos < len(ba) and not ba[pos]:
        zeros += 1
        pos += 1
    # Если дошли до конца, данных больше нет
    if pos >= len(ba):
        return -1, pos
    pos += 1  # пропускаем единицу
    if zeros == 0:
        return 1, pos
    if pos + zeros > len(ba):
        return -1, pos
    rest = 0
    for _ in range(zeros):
        rest = (rest << 1) | ba[pos]
        pos += 1
    return (1 << zeros) | rest, pos


def delta_encode(n: int) -> bitarray:
    if n < 1:
        raise ValueError("n must be >=1")
    k = n.bit_length()
    ba = gamma_encode(k)
    if k > 1:
        rest = n & ((1 << (k - 1)) - 1)
        bits = bin(rest)[2:].zfill(k - 1)
        ba.extend([int(b) for b in bits])
    return ba


def delta_decode(ba: bitarray, pos: int) -> tuple[int, int]:
    k, pos = gamma_decode(ba, pos)
    if k < 0:
        return -1, pos
    if k == 1:
        return 1, pos
    if pos + k - 1 > len(ba):
        return -1, pos
    rest = 0
    for _ in range(k - 1):
        rest = (rest << 1) | ba[pos]
        pos += 1
    return (1 << (k - 1)) | rest, pos


def encode_deltas_gamma(ids: List[int]) -> bytes:
    if not ids:
        return b''
    ba = bitarray()
    ba.extend(gamma_encode(ids[0]))
    prev = ids[0]
    for cur in ids[1:]:
        delta = cur - prev
        ba.extend(gamma_encode(delta))
        prev = cur
    return ba.tobytes()


def decode_deltas_gamma(data: bytes) -> List[int]:
    if not data:
        return []
    ba = bitarray()
    ba.frombytes(data)
    pos = 0
    res = []
    val, pos = gamma_decode(ba, pos)
    if val < 0:
        return res
    res.append(val)
    prev = val
    while pos < len(ba):
        delta, pos = gamma_decode(ba, pos)
        if delta < 0:
            break
        cur = prev + delta
        res.append(cur)
        prev = cur
    return res


def encode_deltas_delta(ids: List[int]) -> bytes:
    if not ids:
        return b''
    ba = bitarray()
    prev = ids[0]
    ba.extend(delta_encode(prev))
    for cur in ids[1:]:
        delta = cur - prev
        ba.extend(delta_encode(delta))
        prev = cur
    return ba.tobytes()


def decode_deltas_delta(data: bytes) -> List[int]:
    if not data:
        return []
    ba = bitarray()
    ba.frombytes(data)
    pos = 0
    val, pos = delta_decode(ba, pos)
    if val < 0:
        return []
    res = [val]
    prev = val
    while pos < len(ba):
        delta, pos = delta_decode(ba, pos)
        if delta < 0:
            break
        cur = prev + delta
        res.append(cur)
        prev = cur
    return res