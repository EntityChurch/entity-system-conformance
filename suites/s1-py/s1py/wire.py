"""TCP framing (ENTITY-CORE-PROTOCOL §1.6), envelopes (§3.1–§3.3) and the connection handshake (§4.1–§4.6).

Every read returns an OUTCOME, never an exception, because what happened on the wire — a coded response,
a close, a timeout, bytes that do not decode — is what a requirement arm is written against. A check
that turns "the peer closed" into a Python traceback has lost the observation.
"""

from __future__ import annotations

import os
import socket
import struct
import time
from dataclasses import dataclass, field

from . import cbor
from .ident import Identity, entity

CONNECT = "system/protocol/connect"
EXECUTE = "system/protocol/execute"
RESPONSE = "system/protocol/execute/response"
PROTOCOL_VERSION = "entity-core/1.0"  # §8.4

# Our reader's own allocation bound. It is not the peer's §4.10(a) bound and asserts nothing about it.
READ_LIMIT = 64 * 1024 * 1024


@dataclass
class Outcome:
    """What one read produced. `kind` is one of: response, execute, other_frame, close, timeout, undecodable — or
    unreachable, when no connection was ever opened (never an observation of the peer, F57)."""

    kind: str
    status: int | None = None
    code: str | None = None
    request_id: str | None = None
    envelope: dict | None = None
    prefix: int | None = None
    raw: bytes | None = None
    detail: str = ""
    findings: cbor.Findings | None = None
    uri: str | None = None
    operation: str | None = None

    def brief(self) -> str:
        if self.kind == "response":
            return f"{self.status} {self.code or '-'} (request_id {self.request_id!r})"
        if self.kind in ("close", "timeout", "undecodable", "unreachable"):
            return f"{self.kind}{': ' + self.detail if self.detail else ''}"
        return f"{self.kind} {self.detail}"


def empty_params() -> dict:
    """§3.2 empty-params wire shape: a primitive/any entity whose data is the empty map."""
    return entity("primitive/any", {})


def tree_get_params() -> dict:
    """§3.9: system/tree get's input type is system/tree/get-request, so it does NOT take the empty-params shape;
    §3.2 lets a handler refuse a mismatched params type 400 unexpected_params. (Found 2026-09-13 by comparing
    suites: this suite first sent primitive/any here, which the weak controls could not detect.)"""
    return entity("system/tree/get-request", {})


def execute_entity(request_id: str, uri: str, operation: str, params: dict | None = None,
                   author: bytes | None = None, capability: bytes | None = None,
                   resource: dict | None = None) -> dict:
    data: dict = {"request_id": request_id, "uri": uri, "operation": operation,
                  "params": params if params is not None else empty_params()}
    # Optional fields are ABSENT when unused, never null (§1.3).
    if resource is not None:
        data["resource"] = resource
    if author is not None:
        data["author"] = author
    if capability is not None:
        data["capability"] = capability
    return entity(EXECUTE, data)


def envelope(root: dict, included: dict | None = None) -> bytes:
    return cbor.encode({"root": root, "included": included or {}})


def frame(payload: bytes, byte_order: str = "big") -> bytes:
    return struct.pack(">I" if byte_order == "big" else "<I", len(payload)) + payload


def request_id(tag: str) -> str:
    return f"cnf-s1py-{tag}-{os.urandom(4).hex()}"


# How many connections this process FAILED TO OPEN. A connection that never opened is not the peer refusing anything: until
# 2026-09-13 (d) such a failure was classified as a close, and a run against an address with no peer behind it scored
# FAILs, INCONCLUSIVEs and one PASS (F57). checks.run() reads this counter around every check and turns any verdict
# reached while it moved into could-not-look.
UNREACHABLE = [0]


class Conn:
    def __init__(self, addr: str, timeout: float):
        host, _, port = addr.rpartition(":")
        self.timeout = timeout
        try:
            self.sock = socket.create_connection((host.strip("[]"), int(port)), timeout=timeout)
        except OSError:
            UNREACHABLE[0] += 1
            raise
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.closed = False

    def close(self):
        if not self.closed:
            try:
                self.sock.close()
            finally:
                self.closed = True

    def send(self, data: bytes) -> str | None:
        try:
            self.sock.sendall(data)
            return None
        except OSError as e:
            return f"send failed: {e}"

    def _read_exact(self, n: int, deadline: float) -> bytes | Outcome:
        buf = bytearray()
        while len(buf) < n:
            left = deadline - time.monotonic()
            if left <= 0:
                return Outcome("timeout", detail=f"{len(buf)} of {n} bytes after {self.timeout:g}s")
            self.sock.settimeout(left)
            try:
                chunk = self.sock.recv(min(n - len(buf), 1 << 20))
            except socket.timeout:
                return Outcome("timeout", detail=f"{len(buf)} of {n} bytes after {self.timeout:g}s")
            except OSError as e:
                return Outcome("close", detail=f"{e.__class__.__name__}: {e}")
            if not chunk:
                return Outcome("close", detail=f"EOF after {len(buf)} of {n} bytes")
            buf += chunk
        return bytes(buf)

    def read(self, timeout: float | None = None) -> Outcome:
        """One §1.6 frame, classified. The prefix is read big-endian and the payload must be EXACTLY one item."""
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        head = self._read_exact(4, deadline)
        if isinstance(head, Outcome):
            return head
        n = struct.unpack(">I", head)[0]
        if n > READ_LIMIT:
            return Outcome("undecodable", prefix=n, detail=f"frame prefix {n} exceeds this reader's {READ_LIMIT}-byte bound")
        body = self._read_exact(n, deadline)
        if isinstance(body, Outcome):
            body.prefix = n
            return body
        return classify(body, n)


def classify(body: bytes, prefix: int | None = None) -> Outcome:
    try:
        value, consumed, findings = cbor.decode_one(body)
    except cbor.CBORError as e:
        return Outcome("undecodable", prefix=prefix, raw=body, detail=str(e))
    if consumed != len(body):
        return Outcome("undecodable", prefix=prefix, raw=body, findings=findings,
                       detail=f"prefix {prefix} covers {len(body)} bytes but the CBOR item is {consumed}")
    root = value.get("root") if isinstance(value, dict) else None
    rtype = root.get("type") if isinstance(root, dict) else None
    data = root.get("data") if isinstance(root, dict) else None
    out = Outcome("other_frame", envelope=value if isinstance(value, dict) else None, prefix=prefix, raw=body,
                  findings=findings, detail=f"root type {rtype!r}")
    if rtype == RESPONSE and isinstance(data, dict):
        out.kind = "response"
        st = data.get("status")
        # `type is int`, not isinstance: in Python `True` is an int, and a peer answering `status: true` has not
        # answered status 1.
        out.status = st if type(st) is int else None
        out.request_id = data.get("request_id") if isinstance(data.get("request_id"), str) else None
        result = data.get("result")
        rdata = result.get("data") if isinstance(result, dict) else None
        if isinstance(rdata, dict) and isinstance(rdata.get("code"), str):
            out.code = rdata["code"]
    elif rtype == EXECUTE and isinstance(data, dict):
        out.kind = "execute"
        out.request_id = data.get("request_id") if isinstance(data.get("request_id"), str) else None
        out.uri = data.get("uri") if isinstance(data.get("uri"), str) else None
        out.operation = data.get("operation") if isinstance(data.get("operation"), str) else None
        out.detail = f"inbound EXECUTE {out.uri!r} {out.operation!r}"
    return out


def result_of(o: Outcome) -> dict | None:
    try:
        r = o.envelope["root"]["data"]["result"]
        return r if isinstance(r, dict) else None
    except (KeyError, TypeError):
        return None


@dataclass
class Session:
    """A connection on which §4.1 legs 1–2 completed. Leg 3 is never requested (§4.1: we are client-style)."""

    conn: Conn
    me: Identity
    sign_message: str
    responder_hello: dict
    token_hash: bytes
    grant_included: dict
    # Inbound EXECUTEs, as (phase, Outcome). phase "handshake" = before the leg-2 response; "session" = after.
    unsolicited: list = field(default_factory=list)
    leg2_at: float = 0.0
    # Every frame the handshake READ, as (label, Outcome) with raw bytes — what the emitted-side requirements inspect.
    received: list = field(default_factory=list)

    def read_response(self, timeout: float | None = None) -> Outcome:
        """The next EXECUTE_RESPONSE. An inbound EXECUTE in between is recorded (§4.1 forbids an unsolicited
        leg 3 to a client-style initiator) and skipped, never answered."""
        while True:
            o = self.conn.read(timeout)
            if o.kind == "execute":
                self.unsolicited.append(("session", o))
                continue
            return o

    def signed(self, rid: str, uri: str, operation: str, resource: dict | None = None,
               params: dict | None = None) -> bytes:
        """A §5.1 authenticated EXECUTE, framed: author, capability, signature and the chain in `included`."""
        if params is None and uri == "system/tree" and operation == "get":
            params = tree_get_params()
        ex = execute_entity(rid, uri, operation, params=params, author=self.me.peer_hash,
                            capability=self.token_hash, resource=resource)
        sig = self.me.signature_entity(ex, self.sign_message)
        included = dict(self.grant_included)
        included[self.me.peer_hash] = self.me.peer_entity
        included[sig["content_hash"]] = sig
        return frame(envelope(ex, included))

    def unauthenticated(self, rid: str, uri: str, operation: str, resource: dict | None = None) -> bytes:
        """No author, no capability, no signature — the §4.2 connect-path shape."""
        params = tree_get_params() if (uri, operation) == ("system/tree", "get") else None
        return frame(envelope(execute_entity(rid, uri, operation, params=params, resource=resource)))


ABSENT = object()  # a hello field OMITTED from the map — a different wire shape from an empty list (§4.5)


def hello_payload(me: Identity, rid: str | None = None, key_types: list[str] | None = None,
                  protocols: list[str] | object = None, hash_formats: list[str] | None = None) -> bytes:
    data = {
        "peer_id": me.peer_id,
        "nonce": os.urandom(32),
        "protocols": [PROTOCOL_VERSION] if protocols is None else protocols,
        "timestamp": int(time.time() * 1000),
    }
    if protocols is ABSENT:  # required with no default (§3.8, §4.5): omitting it is an input some requirements send
        del data["protocols"]
    if key_types is not None:  # optional (§3.8); absent means ["ed25519"] (§4.5)
        data["key_types"] = key_types
    if hash_formats is not None:  # optional (§3.8); absent means ["ecfv1-sha256"] (§4.5)
        data["hash_formats"] = hash_formats
    params = entity("system/protocol/connect/hello", data)
    return envelope(execute_entity(rid or request_id("hello"), CONNECT, "hello", params=params))


def flip_last(h: bytes) -> bytes:
    return h[:-1] + bytes([h[-1] ^ 0x01])


def probe_entity(type_: str, data: object, corrupt: bool = False) -> dict:
    """An entity whose content_hash is computed over the PROBE bytes of {type, data} (tags and duplicate keys included),
    optionally with its final digest byte flipped. Hashing what is actually sent is what keeps a refusal attributable to the
    one defect a probe carries, rather than to a hash mismatch it did not mean to send."""
    import hashlib
    ch = b"\x00" + hashlib.sha256(cbor.encode_probe({"type": type_, "data": data})).digest()
    return {"type": type_, "data": data, "content_hash": flip_last(ch) if corrupt else ch}


def hello_probe(me: Identity, extra: tuple = (), corrupt_root: bool = False, corrupt_params: bool = False,
                included: dict | None = None, wrap_tag: int | None = None) -> bytes:
    """A §3.8 hello with extra data PAIRS appended (a key may repeat; a value may be a Tag), every hash over the bytes sent
    unless told to corrupt one. `wrap_tag` puts a tag around the whole payload. Returns the framed bytes."""
    base = (("peer_id", me.peer_id), ("nonce", os.urandom(32)), ("protocols", [PROTOCOL_VERSION]),
            ("timestamp", int(time.time() * 1000)))
    params = probe_entity("system/protocol/connect/hello", cbor.Pairs(base + tuple(extra)), corrupt=corrupt_params)
    root = probe_entity(EXECUTE, {"request_id": request_id("hello-probe"), "uri": CONNECT, "operation": "hello",
                                  "params": params}, corrupt=corrupt_root)
    env: object = {"root": root, "included": included or {}}
    if wrap_tag is not None:
        env = cbor.Tag(wrap_tag, env)
    return frame(cbor.encode_probe(env))


@dataclass
class HandshakeFailure:
    step: str
    outcome: Outcome

    def brief(self) -> str:
        return f"handshake {self.step}: {self.outcome.brief()}"


def handshake(addr: str, me: Identity, timeout: float, sign_message: str = "hash33",
              key_types: list[str] | None = None) -> Session | HandshakeFailure:
    try:
        conn = Conn(addr, timeout)
    except OSError as e:
        return HandshakeFailure("tcp_open", Outcome("unreachable", detail=f"{e.__class__.__name__}: {e}"))
    hello_rid = request_id("hello")
    err = conn.send(frame(hello_payload(me, hello_rid, key_types)))
    if err:
        return HandshakeFailure("hello", Outcome("close", detail=err))
    o = conn.read()
    received = [("hello response", o)]
    if o.kind != "response" or o.status != 200:
        conn.close()
        return HandshakeFailure("hello", o)
    rh = result_of(o)
    rdata = rh.get("data") if isinstance(rh, dict) else None
    if not isinstance(rdata, dict) or not isinstance(rdata.get("nonce"), bytes):
        conn.close()
        o.detail = "hello response carries no responder nonce"
        return HandshakeFailure("hello", o)

    auth = entity("system/protocol/connect/authenticate", {
        "peer_id": me.peer_id,
        "public_key": me.public_key,
        "key_type": "ed25519",
        "nonce": rdata["nonce"],  # §4.6 step 1: the responder's nonce, echoed
    })
    sig = me.signature_entity(auth, sign_message)
    ex = execute_entity(request_id("authenticate"), CONNECT, "authenticate", params=auth)
    err = conn.send(frame(envelope(ex, {me.peer_hash: me.peer_entity, sig["content_hash"]: sig})))
    if err:
        return HandshakeFailure("authenticate", Outcome("close", detail=err))
    session_unsolicited: list = []
    while True:
        o = conn.read()
        if o.kind == "execute":
            session_unsolicited.append(("handshake", o))
            received.append(("inbound EXECUTE during handshake", o))
            continue
        break
    received.append(("authenticate response", o))
    if o.kind != "response" or o.status != 200:
        conn.close()
        return HandshakeFailure("authenticate", o)
    grant = result_of(o)
    token = grant.get("data", {}).get("token") if isinstance(grant, dict) and isinstance(grant.get("data"), dict) else None
    if not isinstance(token, bytes):
        conn.close()
        o.detail = "authenticate response carries no system/capability/grant token hash"
        return HandshakeFailure("authenticate", o)
    included = o.envelope.get("included") if isinstance(o.envelope.get("included"), dict) else {}
    return Session(conn, me, sign_message, rdata, token, dict(included), session_unsolicited, time.monotonic(), received)
