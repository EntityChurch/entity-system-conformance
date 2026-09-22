"""Content hashes, entities, peer ids and signatures — ENTITY-CORE-PROTOCOL §1.1, §1.2, §1.5, §3.5, §7.1–§7.4."""

from __future__ import annotations

import hashlib
import os

from . import cbor, ed25519

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"  # §8.5


def varint(n: int) -> bytes:
    """Multicodec-style unsigned LEB128 (§7.3)."""
    if n < 0:
        raise ValueError("varint of a negative number")
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def base58(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\x00"))) + s


def base58_decode(text: str) -> bytes:
    n = 0
    for ch in text:
        i = B58.find(ch)
        if i < 0:
            raise ValueError(f"not Base58 (§8.5): {ch!r}")
        n = n * 58 + i
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * (len(text) - len(text.lstrip("1"))) + body


def read_varint(b: bytes, i: int = 0) -> tuple[int, int]:
    n = shift = 0
    while True:
        if i >= len(b):
            raise ValueError("truncated varint")
        byte = b[i]
        n |= (byte & 0x7F) << shift
        i += 1
        if not byte & 0x80:
            return n, i
        shift += 7


KEY_TYPE_NAMES = {0x01: "ed25519", 0x02: "ed448", 0x03: "ml-dsa-65", 0x04: "slh-dsa-sha2-128s", 0x05: "ml-dsa-44",
                  0x06: "ml-dsa-87", 0x07: "falcon-512", 0x08: "slh-dsa-sha2-192s", 0x09: "secp256k1", 0x0A: "p-256",
                  0xFE: "experimental-test"}  # §1.5 two-layer surface table


def parse_peer_id(pid: str) -> tuple[int, int, bytes]:
    """(key_type, hash_type, digest) from a wire peer id (§1.5)."""
    raw = base58_decode(pid)
    kt, i = read_varint(raw)
    ht, i = read_varint(raw, i)
    return kt, ht, raw[i:]


def content_hash(type_: str, data: object, format_code: int = 0x00) -> bytes:
    """§1.2 / §7.1. SHA-256 is the only digest this suite computes; the format code is the caller's."""
    return varint(format_code) + hashlib.sha256(cbor.encode({"type": type_, "data": data})).digest()


def entity(type_: str, data: object) -> dict:
    return {"type": type_, "data": data, "content_hash": content_hash(type_, data)}


def peer_id(public_key: bytes, key_type: int = 0x01, hash_type: int = 0x00) -> str:
    """§7.4. For Ed25519 the canonical hash_type is 0x00 and the digest IS the public key (§1.5)."""
    if hash_type == 0x00:
        digest = public_key
    elif hash_type == 0x01:
        digest = hashlib.sha256(public_key).digest()
    else:
        raise ValueError(f"hash_type {hash_type} has no construction in this snapshot")
    return base58(varint(key_type) + varint(hash_type) + digest)


# Which bytes a signature covers. §7.3 and §4.6 say the full content_hash (format code + digest).
# The others exist only to MEASURE F30 — the ECF corpus's signature.* vectors disagree with §7.3 —
# and are never the default.
SIGN_MESSAGES = ("hash33", "digest32", "ecf")


def signing_message(ent: dict, mode: str) -> bytes:
    if mode == "hash33":
        return ent["content_hash"]
    if mode == "digest32":
        return ent["content_hash"][1:]
    if mode == "ecf":
        return cbor.encode({"type": ent["type"], "data": ent["data"]})
    raise ValueError(f"unknown signing message mode {mode!r}")


class Identity:
    """A throwaway Ed25519 identity for one run. Nothing about it is secret."""

    def __init__(self, seed: bytes | None = None):
        self.seed = seed if seed is not None else os.urandom(32)
        self.public_key = ed25519.public_key(self.seed)
        self.peer_id = peer_id(self.public_key)
        # §3.5 / §4.6: peer_id is NOT in the system/peer hashable basis.
        self.peer_entity = entity("system/peer", {"public_key": self.public_key, "key_type": "ed25519"})
        self.peer_hash = self.peer_entity["content_hash"]

    def signature_entity(self, target: dict, mode: str = "hash33") -> dict:
        sig = ed25519.sign(self.seed, signing_message(target, mode))
        return entity("system/signature", {
            "target": target["content_hash"],
            "signer": self.peer_hash,
            "algorithm": "ed25519",
            "signature": sig,
        })
