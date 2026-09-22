"""Predicates over what a peer EMITS — the passive half of the `encoding` batch.

Each takes decoded frames (or one decoded value) and returns (held, detail, witnesses): held True/False, or None when
nothing in the input was in the requirement's domain (VACUOUS — reported, never a pass). The checks in checks.py run
them over captured traffic, and run them again over fixtures that must fail, which is each requirement's negative
control. Written from ENTITY-CORE-PROTOCOL §1.2, §1.3, §1.11, §2.5, §3.1, §3.5, §3.6 and ENTITY-CBOR-ENCODING §4.1.
"""

from __future__ import annotations

import hashlib

from . import cbor, ident

# §1.2's table: code -> (digest function, digest length). Only what this suite computes; 0x03/0x04 are held back because
# core §1.2 and ENTITY-CBOR-ENCODING §4.3 name different algorithms for them (F20) — lengths agree, algorithms do not.
DIGESTS = {0x00: (hashlib.sha256, 32), 0x01: (hashlib.sha384, 48), 0x02: (hashlib.sha512, 64)}
DISPUTED_CODES = {0x03, 0x04}


def is_entity(v: object) -> bool:
    return isinstance(v, dict) and isinstance(v.get("type"), str) and "data" in v and "content_hash" in v


def entities_of(env: object) -> list[tuple[str, dict]]:
    """The entities an envelope carries at the positions §3.1/§3.3 define: root, the response's result, included values."""
    out: list[tuple[str, dict]] = []
    if not isinstance(env, dict):
        return out
    root = env.get("root")
    if is_entity(root):
        out.append(("root", root))
        data = root.get("data")
        for field in ("result", "params"):
            if isinstance(data, dict) and is_entity(data.get(field)):
                out.append((field, data[field]))
    inc = env.get("included")
    if isinstance(inc, dict):
        for k, e in inc.items():
            if is_entity(e):
                out.append((f"included[{k.hex()[:12] if isinstance(k, bytes) else repr(k)[:14]}]", e))
    return out


def _major(k: object) -> int:
    if k is True or k is False or k is None or isinstance(k, float):
        return 7
    if type(k) is int:
        return 0 if k >= 0 else 1
    return {bytes: 2, str: 3, tuple: 4}.get(type(k), 9)


def mixed_key_types(v: object) -> bool:
    """A map anywhere inside whose keys mix CBOR major types — where ECF Rule 2 and RFC 8949 §4.2.1 order differently."""
    if isinstance(v, dict):
        return len({_major(k) for k in v}) > 1 or any(mixed_key_types(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return any(mixed_key_types(x) for x in v)
    if isinstance(v, cbor.Tag):
        return mixed_key_types(v.value)
    return False


# ── system/hash shape (ECP-R12) ─────────────────────────────────────────────────────────────────

def hash_shape(v: object) -> tuple[bool | None, str]:
    """(True, "") flat and correctly sized · (False, why) not a flat §1.2 hash · (None, why) a code whose length is not
    asserted here (witness). A Tag around correct bytes is NOT flat — unwrapping it first is the defect the control catches."""
    if type(v) is not bytes:
        return False, f"not a byte string: {type(v).__name__} {repr(v)[:40]}"
    try:
        code, i = ident.read_varint(v)
    except ValueError:
        return False, "no decodable leading varint"
    if code in (0x00, 0x01):
        want = i + DIGESTS[code][1]
        return (len(v) == want), (f"code {code:#04x}, {len(v)} bytes" + ("" if len(v) == want else f", §1.2 says {want}"))
    return None, f"code {code:#x}, {len(v)} bytes — length not asserted for this code"


def hash_positions(env: object) -> list[tuple[str, object]]:
    """Every position §2.5/§3 types as system/hash that the suite can name without guessing."""
    out: list[tuple[str, object]] = []
    if isinstance(env, dict) and isinstance(env.get("included"), dict):
        out += [("included map key", k) for k in env["included"]]
    for where, e in entities_of(env):
        out.append(("entity content_hash", e.get("content_hash")))
        d = e.get("data")
        if not isinstance(d, dict):
            continue
        if e["type"] == "system/signature":
            out += [(f"system/signature {f}", d[f]) for f in ("target", "signer") if f in d]
        elif e["type"] == "system/capability/token":
            if "grantee" in d:
                out.append(("system/capability/token grantee", d["grantee"]))
            if d.get("parent") is not None:
                out.append(("system/capability/token parent (when present)", d["parent"]))
            if "granter" in d and not isinstance(d["granter"], dict):  # a map is the multi-granter arm of the union
                out.append(("system/capability/token granter (single-sig form)", d["granter"]))
    return out


def all_hashes_flat(envs: list[object]) -> tuple[bool | None, str, dict]:
    seen: dict[str, int] = {}
    bad, witnessed = [], []
    for env in envs:
        for member, v in hash_positions(env):
            seen[member] = seen.get(member, 0) + 1
            ok, why = hash_shape(v)
            if ok is False:
                bad.append(f"{member}: {why}")
            elif ok is None:
                witnessed.append(f"{member}: {why}")
    w = {"members_observed": seen, "codes_not_asserted": witnessed[:8]}
    if not seen:
        return None, "no hash position observed (vacuous)", w
    return (not bad), ("; ".join(bad[:6]) if bad else f"{sum(seen.values())} hash positions, all flat and sized"), w


# ── content_hash recomputation (ECP-R2) ─────────────────────────────────────────────────────────

def recompute(e: dict) -> tuple[bool | None, str]:
    ch = e.get("content_hash")
    if type(ch) is not bytes:
        return None, f"content_hash is not bytes ({type(ch).__name__}) — ECP-R12's, not recomputed here"
    try:
        code, i = ident.read_varint(ch)
    except ValueError:
        return None, "content_hash has no decodable varint — ECP-R12's"
    if code in DISPUTED_CODES or code not in DIGESTS:
        return None, f"format code {code:#x} not computed by this suite" + (" (F20)" if code in DISPUTED_CODES else "")
    if mixed_key_types(e.get("data")):
        return None, "data holds a map mixing key major types — F22 ordering ambiguity, witnessed"
    try:
        enc = cbor.encode({"type": e["type"], "data": e["data"]})
    except cbor.CBORError as err:
        return None, f"{{type, data}} has no ECF encoding ({err}) — another requirement's"
    fn, _ = DIGESTS[code]
    want = ident.varint(code) + fn(enc).digest()
    return (ch == want), (f"{e['type']} code {code:#04x} recomputes" if ch == want else f"{e['type']}: carried {ch.hex()[:16]}…, recomputed {want.hex()[:16]}…")


def all_hashes_recompute(envs: list[object]) -> tuple[bool | None, str, dict]:
    codes: dict[str, set] = {}
    bad, unscored, n = [], [], 0
    for env in envs:
        for where, e in entities_of(env):
            ok, why = recompute(e)
            ch = e.get("content_hash")
            if type(ch) is bytes and ch:
                codes.setdefault(where.split("[")[0], set()).add(ch[0])
            if ok is None:
                unscored.append(f"{where}: {why}")
            else:
                n += 1
                if not ok:
                    bad.append(f"{where}: {why}")
    w = {"format_codes_seen": {k: sorted(v) for k, v in codes.items()}, "not_scored": unscored[:8]}
    if n == 0:
        return None, "no entity whose hash this suite can recompute (vacuous)", w
    return (not bad), ("; ".join(bad[:6]) if bad else f"{n} emitted entities recompute"), w


# ── included keys (ECP-R7-pending-b) ────────────────────────────────────────────────────────────

def included_keys_match(envs: list[object]) -> tuple[bool | None, str, dict]:
    n, bad = 0, []
    for env in envs:
        inc = env.get("included") if isinstance(env, dict) else None
        if not isinstance(inc, dict):
            continue
        for k, e in inc.items():
            n += 1
            ch = e.get("content_hash") if isinstance(e, dict) else None
            if type(k) is not bytes or k != ch:
                bad.append(f"key {repr(k)[:30]} vs content_hash {repr(ch)[:30]}")
    if n == 0:
        return None, "every observed `included` map is empty (vacuous)", {"included_entries": 0}
    return (not bad), ("; ".join(bad[:4]) if bad else f"{n} included keys equal their entity's content_hash"), {"included_entries": n}


# ── canonical frames (UNALLOCATED-emitted-frames-are-canonical-ecf) ──────────────────────────────

def frame_is_canonical(raw: bytes) -> tuple[bool, str]:
    try:
        value, findings = cbor.decode(raw)
    except cbor.CBORError as err:
        return False, f"not decodable as one well-formed item: {err}"
    try:
        if cbor.encode(value) == raw:
            return True, "re-encodes identically"
        if mixed_key_types(value) and cbor.encode(value, key_order="bytewise") == raw:
            return True, "re-encodes identically under RFC 8949 §4.2.1 bytewise order only (F22, witnessed)"
    except cbor.CBORError as err:
        return False, f"no ECF re-encoding: {err}"
    return False, "re-encoding differs" + (f": {findings.non_canonical[:3]}" if findings.non_canonical else "")


# ── §3 field types (UNALLOCATED-emitted-entities-conform-to-protocol-types) ─────────────────────

def _uint(v: object) -> bool:
    return type(v) is int and v >= 0


def typed_fields(envs: list[object]) -> tuple[bool | None, str, dict]:
    members: dict[str, int] = {}
    bad, nulls = [], []

    def member(name: str, ok: bool, shown: object):
        members[name] = members.get(name, 0) + 1
        if not ok:
            bad.append(f"{name}: got {type(shown).__name__} {repr(shown)[:40]}")

    for env in envs:
        for _, e in entities_of(env):
            d = e.get("data")
            if not isinstance(d, dict):
                continue
            if e["type"] == "system/signature":
                for f in ("signer", "target"):
                    if f in d:
                        member(f"system/signature.{f} is a system/hash", hash_shape(d[f])[0] is not False, d[f])
                if "algorithm" in d:
                    member("system/signature.algorithm is a text string", type(d["algorithm"]) is str, d["algorithm"])
                if "signature" in d:
                    member("system/signature.signature is a byte string", type(d["signature"]) is bytes, d["signature"])
            elif e["type"] == "system/capability/token":
                if "grantee" in d:
                    member("system/capability/token.grantee is a system/hash", hash_shape(d["grantee"])[0] is not False, d["grantee"])
                if "created_at" in d:
                    member("system/capability/token.created_at is an unsigned integer", _uint(d["created_at"]), d["created_at"])
                cav = d.get("delegation_caveats")
                if "delegation_caveats" in d and cav is None:
                    nulls.append("delegation_caveats: null — §1.3 'semantically valid'; the SHOULD file's, not scored here")
                elif "delegation_caveats" in d:
                    ok = isinstance(cav, dict) and all(
                        cav.get(f) is None or check(cav[f])
                        for f, check in (("no_delegation", lambda x: type(x) is bool),
                                         ("max_delegation_depth", _uint), ("max_delegation_ttl", _uint)))
                    member("system/capability/token.delegation_caveats, when present, is a map whose declared fields have their declared types", ok, cav)
    w = {"members_observed": members, "nulls_seen": nulls}
    if not members:
        return None, "no system/signature or system/capability/token field observed (vacuous)", w
    return (not bad), ("; ".join(bad[:6]) if bad else f"{sum(members.values())} typed fields, all of their declared type"), w


# ── optional fields absent, not null (UNALLOCATED-emitted-optional-fields-absent-not-null) ──────

# §3 types a posture-free run meets, and the fields each declares `optional: true`. Undeclared extras are out of scope.
OPTIONAL = {
    "system/protocol/execute/response": ("budget_consumed",),
    "system/protocol/error": ("message",),
    "system/protocol/connect/hello": ("hash_formats", "key_types", "compression", "encryption"),
    "system/capability/token": ("parent", "expires_at", "not_before", "delegation_caveats", "resource_limits"),
}
NESTED = {  # (path within the token, optional fields of the struct found there)
    "grant-entry": ("peers", "constraints", "allowances"),
    "scope": ("exclude",),
    "delegation-caveats": ("no_delegation", "max_delegation_depth", "max_delegation_ttl"),
}


def _structs_of(e: dict) -> list[tuple[str, dict, tuple]]:
    d = e.get("data")
    if not isinstance(d, dict):
        return []
    out = []
    if e["type"] in OPTIONAL:
        out.append((e["type"], d, OPTIONAL[e["type"]]))
    if e["type"] == "system/capability/token":
        if isinstance(d.get("delegation_caveats"), dict):
            out.append(("delegation-caveats", d["delegation_caveats"], NESTED["delegation-caveats"]))
        for i, g in enumerate(d.get("grants") or []):
            if isinstance(g, dict):
                out.append((f"grants[{i}]", g, NESTED["grant-entry"]))
                for dim in ("handlers", "resources", "operations", "peers"):
                    if isinstance(g.get(dim), dict):
                        out.append((f"grants[{i}].{dim}", g[dim], NESTED["scope"]))
    return out


def optional_nulls(envs: list[object]) -> tuple[bool | None, str, dict]:
    nulls, zeros, n = [], [], 0
    for env in envs:
        for where, e in entities_of(env):
            for name, struct, fields in _structs_of(e):
                n += 1
                for f in fields:
                    if f in struct and struct[f] is None:
                        nulls.append(f"{where} {name}.{f}: null")
                    elif f in struct and (struct[f] == 0 and type(struct[f]) is int or struct[f] in ([], {}, b"", "")):
                        zeros.append(f"{where} {name}.{f}: {struct[f]!r}")
    w = {"zero_valued_optionals": zeros[:8], "structs_examined": n}
    if n == 0:
        return None, "no entity of a §3 type this suite knows (vacuous)", w
    return (not nulls), ("; ".join(nulls[:6]) if nulls else f"{n} typed structs, no declared optional field present as null"), w
