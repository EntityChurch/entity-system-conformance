"""Ed25519 (PureEdDSA over edwards25519), written from RFC 8032 §5.1.

Pure Python, stdlib only (hashlib.sha512). Not constant-time: this instrument signs with throwaway keys it
generated for one run, and nothing it holds is secret. `make test` runs it against RFC 8032 §7.1's
vectors, extracted verbatim from the RFC, before it is allowed near a peer.

Verification uses the cofactorless equation [S]B = R + [k]A (RFC 8032 §5.1.7 permits either form) and
rejects S >= L and non-canonical point encodings (§5.1.3, §5.1.7 step 1). Where a peer's signature
verifies under one form and not the other, that is a finding about the peer's library and is reported
as such, never as this module's verdict on the protocol.
"""

from __future__ import annotations

import hashlib

P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, P - 2, P)) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)

# Base point B (RFC 8032 §5.1): y = 4/5, x positive.
_BY = (4 * pow(5, P - 2, P)) % P


def _recover_x(y: int, sign: int) -> int | None:
    # RFC 8032 §5.1.3 steps 2–4.
    if y >= P:
        return None
    x2 = ((y * y - 1) * pow(D * y * y + 1, P - 2, P)) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = (x * SQRT_M1) % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_BX = _recover_x(_BY, 0)
# Extended homogeneous coordinates (X, Y, Z, T) with x = X/Z, y = Y/Z, x*y = T/Z (§5.1.4).
B = (_BX, _BY, 1, (_BX * _BY) % P)
IDENTITY = (0, 1, 1, 0)


def _add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = ((y1 - x1) * (y2 - x2)) % P
    b = ((y1 + x1) * (y2 + x2)) % P
    c = (t1 * 2 * D * t2) % P
    d = (z1 * 2 * z2) % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return ((e * f) % P, (g * h) % P, (f * g) % P, (e * h) % P)


def _mul(s: int, p):
    q = IDENTITY
    while s > 0:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _equal(p, q) -> bool:
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % P == 0 and (y1 * z2 - y2 * z1) % P == 0


def _compress(p) -> bytes:
    x, y, z, _ = p
    zi = pow(z, P - 2, P)
    x, y = (x * zi) % P, (y * zi) % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % P)


def _h(*parts: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b"".join(parts)).digest(), "little")


def _expand(seed: bytes) -> tuple[int, bytes]:
    if len(seed) != 32:
        raise ValueError("Ed25519 private key (seed) is 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(seed: bytes) -> bytes:
    a, _ = _expand(seed)
    return _compress(_mul(a, B))


def sign(seed: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(seed)
    A = _compress(_mul(a, B))
    r = _h(prefix, msg) % L
    R = _compress(_mul(r, B))
    k = _h(R, A, msg) % L
    s = (r + k * a) % L
    return R + int.to_bytes(s, 32, "little")


def verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(pub) != 32 or len(sig) != 64:
        return False
    A = _decompress(pub)
    R = _decompress(sig[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= L:
        return False
    k = _h(sig[:32], pub, msg) % L
    return _equal(_mul(s, B), _add(R, _mul(k, A)))
