#!/usr/bin/env python3
"""CBOR diagnostic notation (RFC 8949 §8) parser + canonical CBOR encoder, for `tools/` ONLY.

    tools/cbordiag.py --self-test

⛔ **THIS IS A SECOND, DELIBERATELY SEPARATE CODEC.** `suites/py-prototype/prototype/cbor.py` is the
one the instrument uses, and `make lint-suite-independence` forbids a suite reaching into `tools/`.
That is not an inconvenience to route around — **shared code is shared bugs, and a shared bug is
exactly what two independent implementations exist to not have.** The two are cross-checked against
each other on the requirement corpus by `make lint-requirements`, and a disagreement between them is
information, not a flake.

Scope, declared: the subset the requirement corpus uses — maps with text keys, arrays, text strings,
integers, booleans, null, and byte strings (`h'…'`). **No floats, no tags, no indefinite lengths.**
A construct outside that subset raises rather than being silently dropped, because a parser that
quietly ignores what it does not understand turns an authoring mistake into missing data that still
digests cleanly.

Canonical form follows `ENTITY-CBOR-ENCODING` §4/§5 and RFC 8949 §4.2.1: definite lengths
throughout, shortest-form arguments, and map keys sorted by their ENCODED BYTES.
"""

from __future__ import annotations

import sys


class DiagError(Exception):
    pass


# ── canonical encoder ─────────────────────────────────────────────────────────────────────────

def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([major << 5 | n])
    for extra, limit, tag in ((1, 1 << 8, 24), (2, 1 << 16, 25), (4, 1 << 32, 26), (8, 1 << 64, 27)):
        if n < limit:
            return bytes([major << 5 | tag]) + n.to_bytes(extra, "big")
    raise DiagError(f"integer out of range: {n}")


def encode(value) -> bytes:
    """Canonical CBOR. Shortest argument, definite length, map keys sorted by encoded bytes."""
    if value is None:
        return b"\xf6"
    if value is True:
        return b"\xf5"
    if value is False:
        return b"\xf4"
    if isinstance(value, int):
        return _head(0, value) if value >= 0 else _head(1, -value - 1)
    if isinstance(value, bytes):
        return _head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(value, (list, tuple)):
        return _head(4, len(value)) + b"".join(encode(v) for v in value)
    if isinstance(value, dict):
        items = sorted(((encode(k), encode(v)) for k, v in value.items()), key=lambda kv: kv[0])
        return _head(5, len(items)) + b"".join(k + v for k, v in items)
    raise DiagError(f"not encodable in the declared subset: {type(value).__name__}")


def decode(raw: bytes):
    """Minimal decoder, for round-tripping the artifact this module wrote."""
    value, off = _decode_at(raw, 0)
    if off != len(raw):
        raise DiagError(f"{len(raw) - off} trailing byte(s)")
    return value


def _decode_at(raw: bytes, off: int):
    if off >= len(raw):
        raise DiagError("truncated")
    ib = raw[off]
    major, ai = ib >> 5, ib & 0x1F
    off += 1
    if ai < 24:
        n = ai
    elif ai in (24, 25, 26, 27):
        width = 1 << (ai - 24)
        n = int.from_bytes(raw[off:off + width], "big")
        off += width
    elif major == 7:
        n = ai
    else:
        raise DiagError(f"indefinite length or reserved additional info {ai} at {off - 1}")
    if major == 0:
        return n, off
    if major == 1:
        return -n - 1, off
    if major == 2:
        return raw[off:off + n], off + n
    if major == 3:
        return raw[off:off + n].decode("utf-8"), off + n
    if major == 4:
        out = []
        for _ in range(n):
            v, off = _decode_at(raw, off)
            out.append(v)
        return out, off
    if major == 5:
        out = {}
        for _ in range(n):
            k, off = _decode_at(raw, off)
            v, off = _decode_at(raw, off)
            out[k] = v
        return out, off
    if major == 7:
        return {20: False, 21: True, 22: None}.get(ai, ...), off
    raise DiagError(f"major type {major} outside the declared subset")


# ── diagnostic-notation parser ────────────────────────────────────────────────────────────────

class _P:
    def __init__(self, text: str):
        self.t, self.i = text, 0

    def err(self, msg):
        line = self.t.count("\n", 0, self.i) + 1
        raise DiagError(f"line {line}: {msg}")

    def ws(self):
        """Whitespace and `/ comment /` markers (RFC 8949 §8)."""
        while self.i < len(self.t):
            c = self.t[self.i]
            if c in " \t\r\n,":
                self.i += 1
            elif c == "/":
                end = self.t.find("/", self.i + 1)
                if end < 0:
                    self.err("unterminated / comment /")
                self.i = end + 1
            else:
                return

    def value(self):
        self.ws()
        if self.i >= len(self.t):
            self.err("expected a value, found end of input")
        c = self.t[self.i]
        if c == "{":
            return self.mapping()
        if c == "[":
            return self.array()
        if c == '"':
            return self.string()
        if c == "h" and self.t[self.i:self.i + 2] == "h'":
            return self.bytestring()
        for word, val in (("true", True), ("false", False), ("null", None)):
            if self.t.startswith(word, self.i):
                self.i += len(word)
                return val
        return self.number()

    def mapping(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.i < len(self.t) and self.t[self.i] == "}":
                self.i += 1
                return out
            k = self.value()
            if not isinstance(k, str):
                self.err(f"map key must be a text string in this subset, got {type(k).__name__}")
            self.ws()
            if self.i >= len(self.t) or self.t[self.i] != ":":
                self.err(f"expected ':' after key {k!r}")
            self.i += 1
            if k in out:
                self.err(f"duplicate map key {k!r} — canonical CBOR has no such map")
            out[k] = self.value()

    def array(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.i < len(self.t) and self.t[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())

    def string(self):
        self.i += 1
        buf = []
        esc = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f",
               "n": "\n", "r": "\r", "t": "\t"}
        while True:
            if self.i >= len(self.t):
                self.err("unterminated string")
            c = self.t[self.i]
            if c == '"':
                self.i += 1
                return "".join(buf)
            if c == "\\":
                nxt = self.t[self.i + 1]
                if nxt == "u":
                    buf.append(chr(int(self.t[self.i + 2:self.i + 6], 16)))
                    self.i += 6
                    continue
                if nxt not in esc:
                    self.err(f"unknown escape \\{nxt}")
                buf.append(esc[nxt])
                self.i += 2
                continue
            if c == "\n":
                self.err("literal newline in a text string — diagnostic notation strings are "
                         "single-line; use \\n, or an array of lines for prose")
            buf.append(c)
            self.i += 1

    def bytestring(self):
        self.i += 2
        end = self.t.find("'", self.i)
        if end < 0:
            self.err("unterminated h'…'")
        hexes = "".join(self.t[self.i:end].split())
        self.i = end + 1
        try:
            return bytes.fromhex(hexes)
        except ValueError as e:
            self.err(f"bad hex in h'…': {e}")

    def number(self):
        j = self.i
        while j < len(self.t) and (self.t[j].isdigit() or self.t[j] in "+-"):
            j += 1
        if j == self.i:
            self.err(f"unexpected {self.t[self.i]!r}")
        text = self.t[self.i:j]
        self.i = j
        try:
            return int(text)
        except ValueError:
            self.err(f"not an integer in the declared subset: {text!r} (no floats)")


def parse(text: str):
    p = _P(text)
    v = p.value()
    p.ws()
    if p.i != len(p.t):
        p.err("trailing content after the top-level value")
    return v


# ── emitter ───────────────────────────────────────────────────────────────────────────────────

def _q(s: str) -> str:
    out = ['"']
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def emit(value, indent: int = 0, _key_order=None) -> str:
    """Diagnostic notation, block-formatted. Key order is AUTHORING order, not encoding order —
    the canonical .cbor sorts keys; this file is for a human, and reordering it to match the
    encoder would make every requirement start with a field nobody reads first."""
    pad, pad2 = "  " * indent, "  " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = [f"{pad2}{_q(k)}: {emit(v, indent + 1)}" for k, v in value.items()]
        return "{\n" + ",\n".join(rows) + f"\n{pad}}}"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        if all(isinstance(v, str) for v in value):
            return "[\n" + ",\n".join(f"{pad2}{_q(v)}" for v in value) + f"\n{pad}]"
        return "[\n" + ",\n".join(f"{pad2}{emit(v, indent + 1)}" for v in value) + f"\n{pad}]"
    if isinstance(value, str):
        return _q(value)
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, bytes):
        return f"h'{value.hex()}'"
    return str(value)


# ── controls ──────────────────────────────────────────────────────────────────────────────────

def self_test() -> int:
    # RFC 8949 §3.4 / Appendix A head encodings.
    for value, expect in [
        (0, "00"), (23, "17"), (24, "1818"), (255, "18ff"), (256, "190100"),
        (-1, "20"), (-24, "37"), (-25, "3818"),
        ("", "60"), ("a", "6161"), ("IETF", "6449455446"),
        (b"", "40"), (b"\x01\x02", "42" "0102"),
        ([], "80"), ([1, 2, 3], "83010203"),
        ({}, "a0"), (True, "f5"), (False, "f4"), (None, "f6"),
    ]:
        got = encode(value).hex()
        if got != expect:
            print(f"SELF-TEST FAILED: encode({value!r}) = {got}, expected {expect}", file=sys.stderr)
            return 1

    # Canonical map ordering: sorted by ENCODED KEY BYTES, so "b" precedes "aa" (length first).
    if encode({"aa": 1, "b": 2}).hex() != "a26162026261610" + "1":
        print(f"SELF-TEST FAILED: map key ordering — got {encode({'aa': 1, 'b': 2}).hex()}, "
              f"expected keys sorted by encoded bytes ('b' before 'aa')", file=sys.stderr)
        return 1
    # ...and authoring order must not change the bytes. This is the property that makes the
    # corpus digest a CONTENT digest rather than a record of what order someone typed in.
    if encode({"aa": 1, "b": 2}) != encode({"b": 2, "aa": 1}):
        print("SELF-TEST FAILED: two authoring orders of the same map encoded differently. The "
              "corpus digest would then measure typing order, not content.", file=sys.stderr)
        return 1

    # Parser: comments, escapes, nesting, bytes.
    got = parse('''
        / a comment /
        { "id": "ECP-R1", "n": -3, "ok": true, "nil": null,
          "lines": [ "one", "two \\"quoted\\"" ],
          "raw": h'01ff' }
    ''')
    want = {"id": "ECP-R1", "n": -3, "ok": True, "nil": None,
            "lines": ["one", 'two "quoted"'], "raw": b"\x01\xff"}
    if got != want:
        print(f"SELF-TEST FAILED: parse -> {got!r}, expected {want!r}", file=sys.stderr)
        return 1

    # Round trip through the emitter.
    if parse(emit(want)) != want:
        print(f"SELF-TEST FAILED: emit/parse round trip lost data: {parse(emit(want))!r}",
              file=sys.stderr)
        return 1
    if decode(encode(want)) != want:
        print(f"SELF-TEST FAILED: encode/decode round trip lost data", file=sys.stderr)
        return 1

    # Refusals. Each is a defect that would otherwise digest cleanly while meaning something else.
    for label, text in [
        ("a duplicate map key", '{ "a": 1, "a": 2 }'),
        ("an unterminated comment", '{ "a": 1 } / oops'),
        ("a literal newline inside a string", '{ "a": "one\ntwo" }'),
        ("a float, which is outside the declared subset", '{ "a": 1.5 }'),
        ("a non-text map key", '{ 1: "a" }'),
        ("trailing content", '{ "a": 1 } { "b": 2 }'),
    ]:
        try:
            parse(text)
        except DiagError:
            continue
        print(f"SELF-TEST FAILED: {label} parsed clean. A parser that ignores what it does not "
              f"understand turns an authoring mistake into missing data that still digests.",
              file=sys.stderr)
        return 1

    print("cbordiag self-test: OK — RFC 8949 head encodings, canonical map ordering "
          "(authoring order does not move the bytes), parse/emit/encode/decode round trips, "
          "6 malformed inputs refused")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv[1:] else 0)
