"""CBOR per RFC 8949, and ECF per ENTITY-CBOR-ENCODING §4.1 — written from those two documents.

Encoding is always canonical (ECF): minimal heads, definite lengths, map keys ordered by encoded length
then bytewise, shortest float that preserves the value, and no tags (§6.3).

Decoding is structural and REPORTING: it accepts any well-formed CBOR item and records, rather than
hides, everything that is not ECF — tags, indefinite lengths, non-minimal heads, unsorted keys,
non-shortest floats. Whether a finding refuses the input is the caller's decision, because what is
refused is a requirement's question, not a codec's.

Three things this module refuses outright, because a Python value cannot represent them faithfully and
a silent collapse would be a measurement defect of ours, not a property of the peer:

  * a DUPLICATE map key (ECF Rule 5; also RFC 8949 §5.6 invalid), detected on the encoded key bytes;
  * two DISTINCT keys Python would merge — the integer 1, the float 1.0 and `true` hash equal in a
    dict. RFC 8949 treats them as different keys. Found by writing this module in Python, which is the
    kind of language idiom this suite exists to notice rather than inherit;
  * invalid UTF-8 in a text string (ENTITY-CBOR-ENCODING §9.2 item 5).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field


class CBORError(ValueError):
    pass


@dataclass(frozen=True)
class Tag:
    number: int
    value: object


class Undefined:
    """Simple value 23. Distinct from None (null). ECF does not use it (ENTITY-CBOR-ENCODING §3.5)."""

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self):
        return "undefined"


@dataclass(frozen=True)
class Simple:
    value: int


UNDEFINED = Undefined()


# ── encoding ────────────────────────────────────────────────────────────────────────────────────

def _head(major: int, arg: int) -> bytes:
    if arg < 0:
        raise CBORError("negative head argument")
    if arg < 24:
        return bytes([(major << 5) | arg])
    if arg < 1 << 8:
        return bytes([(major << 5) | 24, arg])
    if arg < 1 << 16:
        return bytes([(major << 5) | 25]) + arg.to_bytes(2, "big")
    if arg < 1 << 32:
        return bytes([(major << 5) | 26]) + arg.to_bytes(4, "big")
    if arg < 1 << 64:
        return bytes([(major << 5) | 27]) + arg.to_bytes(8, "big")
    raise CBORError(f"integer {arg} does not fit a CBOR head; bignums are tags and ECF has no tags (§6.3)")


def _float(x: float) -> bytes:
    if math.isnan(x):
        return b"\xf9\x7e\x00"  # Rule 4a: the one canonical NaN
    for fmt, prefix in ((">e", b"\xf9"), (">f", b"\xfa")):
        try:
            packed = struct.pack(fmt, x)
        except OverflowError:
            continue
        if struct.unpack(fmt, packed)[0] == x:
            return prefix + packed
    return b"\xfb" + struct.pack(">d", x)


def encode(v: object) -> bytes:
    # bool before int: in Python `True` IS an int, and CBOR true is not the integer 1.
    if v is True:
        return b"\xf5"
    if v is False:
        return b"\xf4"
    if v is None:
        return b"\xf6"
    if isinstance(v, int):
        return _head(0, v) if v >= 0 else _head(1, -1 - v)
    if isinstance(v, float):
        return _float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return _head(2, len(b)) + b
    if isinstance(v, str):
        b = v.encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(v, (list, tuple)):
        return _head(4, len(v)) + b"".join(encode(x) for x in v)
    if isinstance(v, dict):
        items = [(encode(k), encode(val)) for k, val in v.items()]
        items.sort(key=lambda kv: (len(kv[0]), kv[0]))  # ECF Rule 2: length first, then bytewise
        for (a, _), (b, _) in zip(items, items[1:]):
            if a == b:
                raise CBORError("duplicate map key after encoding (ECF Rule 5)")
        return _head(5, len(items)) + b"".join(k + val for k, val in items)
    if isinstance(v, Tag):
        raise CBORError(f"refusing to encode tag {v.number}: ECF forbids tags on the wire (§6.3)")
    if v is UNDEFINED:
        return b"\xf7"
    raise CBORError(f"cannot encode {type(v).__name__}")


# ── decoding ────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Findings:
    """Everything about the input that is not ECF. Empty means the bytes were already canonical as parsed."""

    tags: list[int] = field(default_factory=list)
    non_canonical: list[str] = field(default_factory=list)

    def add(self, why: str):
        if len(self.non_canonical) < 32:
            self.non_canonical.append(why)


class _Reader:
    def __init__(self, data: bytes, max_depth: int):
        self.b = data
        self.i = 0
        self.f = Findings()
        self.max_depth = max_depth

    def take(self, n: int) -> bytes:
        if self.i + n > len(self.b):
            raise CBORError(f"truncated: need {n} bytes at offset {self.i}, have {len(self.b) - self.i}")
        out = self.b[self.i:self.i + n]
        self.i += n
        return out

    def arg(self, ai: int, major: int) -> int | None:
        if ai < 24:
            return ai
        if ai in (24, 25, 26, 27):
            n = 1 << (ai - 24)
            val = int.from_bytes(self.take(n), "big")
            if major != 7:
                minimal = 0 if val < 24 else 1 if val < 1 << 8 else 2 if val < 1 << 16 else 4 if val < 1 << 32 else 8
                if n != minimal:
                    self.f.add(f"non-minimal head (major {major}, {n}-byte argument for {val})")
            return val
        if ai == 31:
            return None
        raise CBORError(f"reserved additional information {ai} (RFC 8949 §3)")

    def item(self, depth: int = 0) -> object:
        if depth > self.max_depth:
            raise CBORError(f"nesting deeper than {self.max_depth}")
        ib = self.take(1)[0]
        major, ai = ib >> 5, ib & 0x1F
        if major == 7:
            return self.simple(ai)
        a = self.arg(ai, major)
        if major == 0:
            if a is None:
                raise CBORError("indefinite length on an integer")
            return a
        if major == 1:
            if a is None:
                raise CBORError("indefinite length on an integer")
            return -1 - a
        if major in (2, 3):
            if a is None:
                self.f.add("indefinite-length string (ECF Rule 3)")
                chunks = []
                while True:
                    nb = self.take(1)[0]
                    if nb == 0xFF:
                        break
                    if nb >> 5 != major:
                        raise CBORError("indefinite string chunk of a different major type")
                    n = self.arg(nb & 0x1F, major)
                    if n is None:
                        raise CBORError("nested indefinite string chunk")
                    chunks.append(self.take(n))
                raw = b"".join(chunks)
            else:
                raw = self.take(a)
            if major == 2:
                return raw
            try:
                return raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as e:
                raise CBORError(f"invalid UTF-8 in text string: {e}") from None
        if major == 4:
            out = []
            if a is None:
                self.f.add("indefinite-length array (ECF Rule 3)")
                while self.b[self.i:self.i + 1] != b"\xff":
                    out.append(self.item(depth + 1))
                self.take(1)
            else:
                for _ in range(a):
                    out.append(self.item(depth + 1))
            return out
        if major == 5:
            return self.map(a, depth)
        if major == 6:
            if a is None:
                raise CBORError("indefinite length on a tag")
            self.f.tags.append(a)
            return Tag(a, self.item(depth + 1))
        raise CBORError("unreachable major type")

    def map(self, count: int | None, depth: int) -> dict:
        if count is None:
            self.f.add("indefinite-length map (ECF Rule 3)")
        out: dict = {}
        seen: set[bytes] = set()
        prev: bytes | None = None
        n = 0
        while True:
            if count is None:
                if self.b[self.i:self.i + 1] == b"\xff":
                    self.take(1)
                    break
            elif n == count:
                break
            start = self.i
            k = self.item(depth + 1)
            kbytes = self.b[start:self.i]
            v = self.item(depth + 1)
            n += 1
            if kbytes in seen:
                raise CBORError(f"duplicate map key {k!r} (ECF Rule 5)")
            seen.add(kbytes)
            try:
                hkey = k if not isinstance(k, list) else tuple(k)
                if hkey in out:
                    raise CBORError(f"distinct CBOR keys collapse to one Python key {k!r} (1 / 1.0 / true); "
                                    "not representable without loss")
            except TypeError:
                raise CBORError(f"map key of type {type(k).__name__} is not representable") from None
            # Order is judged on the canonical encoding of the key, so a non-minimal key head does not
            # also read as a sort violation.
            try:
                canon = encode(k)
            except CBORError:
                canon = kbytes
            if prev is not None and (len(canon), canon) <= (len(prev), prev):
                self.f.add("map keys not in length-then-bytewise order (ECF Rule 2)")
            prev = canon
            out[hkey] = v
        return out

    def simple(self, ai: int) -> object:
        if ai < 20:
            return Simple(ai)
        if ai == 20:
            return False
        if ai == 21:
            return True
        if ai == 22:
            return None
        if ai == 23:
            return UNDEFINED
        if ai == 24:
            v = self.take(1)[0]
            if v < 32:
                raise CBORError("simple value < 32 in two-byte form (RFC 8949 §3.3)")
            return Simple(v)
        if ai in (25, 26, 27):
            n = 1 << (ai - 24)
            fmt = {2: ">e", 4: ">f", 8: ">d"}[n]
            raw = self.take(n)
            x = struct.unpack(fmt, raw)[0]
            if _float(x) != bytes([0xE0 | ai]) + raw:
                self.f.add(f"float {x!r} not in its shortest / canonical form (ECF Rule 4 / 4a)")
            return x
        if ai == 31:
            raise CBORError("unexpected break")
        raise CBORError(f"reserved simple additional information {ai}")


def decode_one(data: bytes, max_depth: int = 256) -> tuple[object, int, Findings]:
    """One item from the start of `data`: (value, bytes consumed, findings). Trailing bytes are the caller's."""
    r = _Reader(bytes(data), max_depth)
    v = r.item()
    return v, r.i, r.f


def decode(data: bytes, max_depth: int = 256) -> tuple[object, Findings]:
    """Exactly one item that consumes all of `data`."""
    v, n, f = decode_one(data, max_depth)
    if n != len(data):
        raise CBORError(f"{len(data) - n} trailing bytes after one complete item")
    return v, f
