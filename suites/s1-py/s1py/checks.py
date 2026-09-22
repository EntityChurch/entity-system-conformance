"""One function per requirement file. Each arm is named as in its TOML, and the verdict follows the file's arms.

Verdicts:
  PASS          the conformant arm held AND the negative control discriminated
  FAIL          the conformant arm was refused, or an assertion the file makes did not hold
  INCONCLUSIVE  the conformant arm held but the control did NOT discriminate — never a pass
  SKIP          a declared precondition was unmet, the suite could not look, or the peer produced an outcome
                the requirement's arms do not classify. The last is a finding about the REQUIREMENT, and is
                reported as one: we do not decide what an unenumerated outcome means (prohibition 2).
"""

from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, field

from . import wire
from . import ident
from .ident import Identity


@dataclass
class Arm:
    kind: str  # conformant | negative-control
    name: str
    held: bool | None  # None = not evaluable (could not look / unclassified / precondition)
    outcome: str


@dataclass
class Result:
    requirement_id: str
    suite_check: str
    spec_ref: str
    verdict: str = "SKIP"
    message: str = ""
    arms: list[Arm] = field(default_factory=list)
    witnesses: dict = field(default_factory=dict)
    peer_attributable: bool = True


@dataclass
class Ctx:
    addr: str
    timeout: float
    sign_message: str
    pre_dispatch_layer: bool
    quiet_wait: float  # how long "no response" is waited for, in the arms that accept it


def _handshake(ctx: Ctx, res: Result) -> wire.Session | None:
    s = wire.handshake(ctx.addr, Identity(), ctx.timeout, ctx.sign_message)
    if isinstance(s, wire.HandshakeFailure):
        res.verdict = "SKIP"
        res.message = f"could not look: {s.brief()} (signing message {ctx.sign_message})"
        res.witnesses["handshake"] = s.brief()
        return None
    res.witnesses["handshake_grants"] = observed_grants(s)
    return s


def observed_grants(s: wire.Session) -> object:
    """The posture AS OBSERVED ON THE WIRE: the grant entries of the capability the handshake actually issued (§4.4).
    The harness's launch flags say what the operator asked for; this says what the peer delivered. Recorded on every
    result that ran on a session, so no verdict depends on a posture read only from someone's launch script."""
    token = s.grant_included.get(s.token_hash)
    grants = token.get("data", {}).get("grants") if isinstance(token, dict) and isinstance(token.get("data"), dict) else None
    if not isinstance(grants, list):
        return "token not found in the authenticate response's included map"
    out = []
    for g in grants:
        if not isinstance(g, dict):
            out.append(repr(g))
            continue
        dims = []
        for dim in ("handlers", "resources", "operations", "peers"):
            v = g.get(dim)
            if isinstance(v, dict):
                dims.append(f"{dim}={v.get('include')}" + (f"-{v.get('exclude')}" if v.get("exclude") else ""))
        out.append(" ".join(dims))
    return out


def _scope_has(scope: object, value: str) -> bool:
    """APPROXIMATE §5.4 matching — exact, "*", or a trailing-"*" prefix; excludes honoured the same way. Used only to
    RECORD whether a declared precondition held, never to score: the full §5.4 matcher is a requirement set of its own."""
    if not isinstance(scope, dict):
        return False
    def hit(pats):
        return any(isinstance(p, str) and (p == value or p == "*" or (p.endswith("*") and value.startswith(p[:-1])))
                   for p in (pats or []))
    return hit(scope.get("include")) and not hit(scope.get("exclude"))


def grant_covers(s: wire.Session, handler: str, operation: str) -> bool | None:
    token = s.grant_included.get(s.token_hash)
    grants = token.get("data", {}).get("grants") if isinstance(token, dict) and isinstance(token.get("data"), dict) else None
    if not isinstance(grants, list):
        return None
    return any(isinstance(g, dict) and _scope_has(g.get("handlers"), handler) and _scope_has(g.get("operations"), operation)
               for g in grants)


def _finish(res: Result, conformant: Arm, control: Arm | None):
    res.arms = [a for a in (conformant, control) if a is not None]
    if conformant.held is False:
        res.verdict = "FAIL"
    elif conformant.held is None:
        res.verdict = "SKIP"
    elif control is None or control.held is None:
        res.verdict = "INCONCLUSIVE"
    elif control.held:
        res.verdict = "PASS"
    else:
        res.verdict = "INCONCLUSIVE"
    if not res.message:
        res.message = f"{conformant.name}: {conformant.outcome}" + (f" | {control.name}: {control.outcome}" if control else "")


# ── ECP-R1 — §1.6 framing ──────────────────────────────────────────────────────────────────────

def check_r1(ctx: Ctx) -> Result:
    res = Result("ECP-R1", "connectivity/r1_tcp_framing_big_endian", "ENTITY-CORE-PROTOCOL §1.6")
    me = Identity()

    # Conformant arm: frame a hello big-endian; the answer's prefix must equal exactly one CBOR item.
    try:
        c = wire.Conn(ctx.addr, ctx.timeout)
    except OSError as e:
        res.message = f"could not look: tcp_open failed: {e}"
        return res
    c.send(wire.frame(wire.hello_payload(me)))
    o = c.read()
    c.close()
    if o.kind == "response":
        ok = o.envelope is not None and o.envelope.get("root", {}).get("type") == wire.RESPONSE
        conformant = Arm("conformant", "framed-hello-answered-framed", ok,
                         f"prefix {o.prefix} = one CBOR item of {len(o.raw)} bytes; EXECUTE_RESPONSE {o.status} {o.code or ''}".strip())
        res.witnesses["hello_status"] = o.status
    elif o.kind == "undecodable" and o.raw is not None:
        conformant = Arm("conformant", "framed-hello-answered-framed", False, f"response frame does not delimit one item: {o.detail}")
    elif o.kind in ("other_frame", "execute"):
        conformant = Arm("conformant", "framed-hello-answered-framed", False, f"answer is not an EXECUTE_RESPONSE envelope: {o.detail}")
    else:
        conformant = Arm("conformant", "framed-hello-answered-framed", False, f"no framed answer to a big-endian hello: {o.brief()}")

    # Control: the IDENTICAL payload with a little-endian prefix. The payload length is padded (via the
    # request_id) until its low byte is >= 2, so the big-endian reading of the LE prefix exceeds 16 MiB,
    # and the two byte orders differ.
    pad = 0
    while True:
        payload = wire.hello_payload(me, wire.request_id("le") + "x" * pad)
        if len(payload) & 0xFF >= 2 and len(payload) < 1 << 16:
            break
        pad += 1
    be_reading = int.from_bytes(len(payload).to_bytes(4, "little"), "big")
    res.witnesses["control_payload_len"] = len(payload)
    res.witnesses["control_le_prefix_read_big_endian"] = be_reading
    try:
        c = wire.Conn(ctx.addr, ctx.timeout)
    except OSError as e:
        control = Arm("negative-control", "control", None, f"could not look: tcp_open failed: {e}")
        _finish(res, conformant, control)
        return res
    c.send(wire.frame(payload, "little"))
    o = c.read(ctx.quiet_wait)
    c.close()
    if o.kind == "response" and o.status == 200:
        control = Arm("negative-control", "control", False, "the little-endian hello was answered as a hello — the prefix did not delimit the frame")
    elif o.kind == "timeout":
        control = Arm("negative-control", "control", True, f"no response within {ctx.quiet_wait:g}s (a big-endian reader waiting on {be_reading} bytes)")
    elif o.kind == "close":
        control = Arm("negative-control", "control", True, f"close ({o.detail})")
    elif o.kind == "response" and o.status == 413 and o.code == "payload_too_large":
        control = Arm("negative-control", "control", True, "413 payload_too_large (§4.10(a))")
    else:
        # The file: "The assertion is only that the hello is NOT answered as a hello." Held, with the
        # outcome recorded because it is outside the file's enumerated accepts.
        control = Arm("negative-control", "control", True, f"not answered as a hello; outcome outside the enumerated accepts: {o.brief()}")
        res.witnesses["control_unenumerated_outcome"] = o.brief()
    _finish(res, conformant, control)
    return res


# ── ECP-R6 — request_id echo ───────────────────────────────────────────────────────────────────

def _classify_for_r6(o: wire.Outcome) -> str | None:
    """What a response ANSWERS, from its content alone. Never from its request_id."""
    if o.kind != "response":
        return None
    r = wire.result_of(o)
    if o.status == 404 and o.code == "handler_not_found":
        return "unregistered"
    if isinstance(r, dict) and r.get("type") == "system/tree/listing" and isinstance(r.get("data"), dict):
        path = r["data"].get("path")
        if isinstance(path, str):
            p = path.rstrip("/")
            if p.endswith("system/type"):
                return "listing-type"
            if p.endswith("system/handler"):
                return "listing-handler"
    return None


def match_by_content(requests: dict[str, str], responses: list[wire.Outcome]) -> tuple[bool | None, str]:
    """requests: request_id -> the content class its answer must have. Returns (held, detail); held None =
    the responses are not distinguishable by content, so the echo cannot be judged without trusting the id."""
    by_class: dict[str, list[wire.Outcome]] = {}
    for o in responses:
        cls = _classify_for_r6(o)
        if cls is None:
            return None, f"a response is not attributable by content: {o.brief()}"
        by_class.setdefault(cls, []).append(o)
    if any(len(v) != 1 for v in by_class.values()) or len(by_class) != len(requests):
        return None, f"responses not one-per-request by content: { {k: len(v) for k, v in by_class.items()} }"
    wrong = []
    for rid, cls in requests.items():
        got = by_class[cls][0].request_id
        if got != rid:
            wrong.append(f"the {cls} answer carries {got!r}, its request was {rid!r}")
    return (not wrong), ("; ".join(wrong) if wrong else "every response carries the request_id of the request it answers")


def check_r6(ctx: Ctx) -> Result:
    res = Result("ECP-R6", "connectivity/r6_request_id_echoed_pipelined", "ENTITY-CORE-PROTOCOL §3.2")
    s = _handshake(ctx, res)
    if s is None:
        return res
    # The file's ids: non-UUID, different lengths. One request is to an unregistered path (an error answer).
    probe = f"conformance-probe/unregistered/{os.urandom(6).hex()}"
    plan = [
        ("cnf-rid-a-7f3e", "system/tree", {"targets": ["system/type/"]}, "listing-type"),
        ("cnf-rid-b-01", probe, None, "unregistered"),
        ("cnf-rid-c-x", "system/tree", {"targets": ["system/handler/"]}, "listing-handler"),
    ]
    err = s.conn.send(b"".join(s.signed(rid, uri, "get", resource=r) for rid, uri, r, _ in plan))
    responses = []
    if not err:
        for _ in plan:
            o = s.read_response()
            if o.kind != "response":
                break
            responses.append(o)
    s.conn.close()
    res.witnesses["responses"] = [o.brief() for o in responses]
    if err or len(responses) != len(plan):
        conformant = Arm("conformant", "echoed", None, f"could not look: {err or 'fewer responses than requests'}")
        _finish(res, conformant, None)
        res.message = conformant.outcome
        return res
    requests = {rid: cls for rid, _, _, cls in plan}
    held, detail = match_by_content(requests, responses)
    conformant = Arm("conformant", "echoed", held, detail)

    # Control, suite-side, over the SAME responses with their request_ids rotated a->b->c->a. A matcher that
    # paired responses by the id they carry would pass this; ours must fail it.
    control = None
    if held is not None:
        rotated = []
        ids = [o.request_id for o in responses]
        for i, o in enumerate(responses):
            rotated.append(wire.Outcome(**{**o.__dict__, "request_id": ids[(i + 1) % len(ids)]}))
        c_held, c_detail = match_by_content(requests, rotated)
        control = Arm("negative-control", "control", c_held is False,
                      "the matcher refused the rotated fixture" if c_held is False else f"the matcher did NOT refuse the rotated fixture: {c_detail}")
    else:
        res.message = f"could not look: {detail} — the file requires matching by content, never by arrival order or id"
    _finish(res, conformant, control)
    return res


# ── ECP-R9 — the connect path is pre-authorized after establishment ────────────────────────────

def check_r9(ctx: Ctx) -> Result:
    res = Result("ECP-R9", "connectivity/r9_connect_path_preauthorized_post_establishment", "ENTITY-CORE-PROTOCOL §4.2")
    s = _handshake(ctx, res)
    if s is None:
        return res
    s.conn.send(s.unauthenticated(wire.request_id("ping"), wire.CONNECT, "ping"))
    o = s.read_response()
    res.witnesses["status_and_code"] = o.brief()
    if o.kind == "close":
        conformant = Arm("conformant", "post-establishment-unauthenticated-connect", False, f"refused by close ({o.detail})")
    elif o.kind == "response" and o.status in (401, 403):
        conformant = Arm("conformant", "post-establishment-unauthenticated-connect", None,
                         f"{o.status} {o.code} — auth-class refusal, a WITNESS pending F10's second question, not scored")
        res.witnesses["auth_class_refusal"] = o.brief()
    elif o.kind == "response" and o.status is not None:
        conformant = Arm("conformant", "post-establishment-unauthenticated-connect", True,
                         f"served, not refused for the absence of author/capability/signature: {o.status} {o.code or ''}".strip())
    else:
        conformant = Arm("conformant", "post-establishment-unauthenticated-connect", None,
                         f"outcome the file's arms do not classify: {o.brief()} — a requirement gap, not a verdict")
        res.witnesses["unclassified"] = o.brief()

    control = None
    if o.kind == "response":
        s.conn.send(s.unauthenticated(wire.request_id("tree"), "system/tree", "get"))
        t = s.read_response()
        res.witnesses["control"] = t.brief()
        if t.kind == "response":
            control = Arm("negative-control", "control", t.status == 401, f"unauthenticated system/tree get: {t.status} {t.code or ''}".strip())
        else:
            control = Arm("negative-control", "control", None, f"could not look: {t.brief()}")
    s.conn.close()
    _finish(res, conformant, control)
    return res


# ── ECP-R44 — 501 unsupported_operation ────────────────────────────────────────────────────────

R44_SYNONYMS = {"unknown_operation", "not_implemented", "not_supported", "not_available"}


def check_r44(ctx: Ctx) -> Result:
    res = Result("ECP-R44", "connectivity/r44_unsupported_operation_on_registered_handler", "ENTITY-CORE-PROTOCOL §3.3")
    s = _handshake(ctx, res)
    if s is None:
        return res
    covered = grant_covers(s, "system/tree", "conformance-probe-undefined-op")
    res.witnesses["precondition_grant_covers_probe"] = covered
    if covered is False:
        # Declared precondition: a grant covering the probe op, so BOTH F19 readings predict 501. Unmet, a 501 shows
        # the peer resolves the manifest before check_permission (§6.2's reading) and a 403 shows the reverse
        # (§6.5/§6.7). The file scores neither reading; this records which one the peer took.
        res.witnesses["f19_order_observable"] = "grant does not cover the probe operation: 501 = manifest-first, 403 = permission-first"
    s.conn.send(s.signed(wire.request_id("undefined-op"), "system/tree", "conformance-probe-undefined-op"))
    o = s.read_response()
    res.witnesses["probe"] = o.brief()
    name = "unimplemented-op"
    if o.kind != "response":
        conformant = Arm("conformant", name, False, f"no coded answer: {o.brief()}")
    elif o.status == 403:
        conformant = Arm("conformant", name, None, f"403 {o.code} — precondition unmet (the grant does not cover the probe operation); SKIP, grant recorded")
        res.witnesses["code_if_403"] = o.code
    elif o.status == 400 and o.code == "unknown_operation":
        conformant = Arm("conformant", name, False, "400 unknown_operation — §6.2's recorded defect")
    elif o.status == 501 and o.code in R44_SYNONYMS:
        conformant = Arm("conformant", name, False, f"501 {o.code} — a synonym of the row's default in the code slot")
    elif o.status == 404 and o.code == "handler_not_found":
        conformant = Arm("conformant", name, False, "404 handler_not_found — the tree handler IS registered")
    elif o.status == 501 and o.code == "unsupported_operation":
        conformant = Arm("conformant", name, True, "501 unsupported_operation")
    else:
        conformant = Arm("conformant", name, False, f"{o.status} {o.code} — status/code assertion (501 unsupported_operation) does not hold")

    control = None
    if o.kind == "response":
        s.conn.send(s.signed(wire.request_id("defined-op"), "system/tree", "get"))
        t = s.read_response()
        res.witnesses["control"] = t.brief()
        if t.kind == "response":
            control = Arm("negative-control", "control", t.code != "unsupported_operation", f"system/tree get: {t.status} {t.code or ''}".strip())
        else:
            control = Arm("negative-control", "control", None, f"could not look: {t.brief()}")
    s.conn.close()
    _finish(res, conformant, control)
    return res


# ── ECP-R45 — 404 handler_not_found ────────────────────────────────────────────────────────────

def check_r45(ctx: Ctx) -> Result:
    res = Result("ECP-R45", "connectivity/r45_handler_not_found_on_unregistered_path", "ENTITY-CORE-PROTOCOL §3.3")
    s = _handshake(ctx, res)
    if s is None:
        return res
    root = "conformance-probe"
    # read_handler_index: decides between the arm and the declared SKIP. Not asserted on.
    s.conn.send(s.signed(wire.request_id("index"), "system/tree", "get", resource={"targets": ["system/handler/"]}))
    idx = s.read_response()
    listing = wire.result_of(idx) if idx.kind == "response" else None
    entries = None
    if isinstance(listing, dict) and listing.get("type") == "system/tree/listing" and isinstance(listing.get("data"), dict):
        e = listing["data"].get("entries")
        if isinstance(e, dict):
            entries = sorted(str(k) for k in e)
    res.witnesses["handler_index"] = entries if entries is not None else f"unreadable: {idx.brief()}"
    catch_all = [n for n in (entries or []) if n in ("", "*", "**", root)]
    if catch_all:
        s.conn.close()
        conformant = Arm("conformant", "no-handler", None, f"a registered pattern could match the probe path: {catch_all} — declared SKIP naming it (§3.3 satisfaction mode)")
        _finish(res, conformant, None)
        res.message = conformant.outcome
        return res

    probe = f"{root}/unregistered/{os.urandom(6).hex()}"
    covered = grant_covers(s, probe, "get")
    # The file runs this under the NARROWEST authority so resolution-first is discriminated from permission-first.
    # A grant that covers the probe path cannot discriminate them; the verdict stands, the ordering half is recorded.
    res.witnesses["precondition_narrow_authority"] = (covered is False) if covered is not None else "grant unreadable"
    if covered:
        res.witnesses["ordering_not_discriminated"] = "the observed grant covers the probe path; a permission-first peer would also answer 404"
    s.conn.send(s.signed(wire.request_id("unregistered"), probe, "get"))
    o = s.read_response()
    res.witnesses["probe"] = f"{probe}: {o.brief()}"
    name = "no-handler"
    if o.kind != "response":
        conformant = Arm("conformant", name, False, f"no coded answer: {o.brief()}")
    elif o.status == 404 and o.code == "handler_not_found":
        conformant = Arm("conformant", name, True, "404 handler_not_found")
    elif o.status == 403 and ctx.pre_dispatch_layer:
        conformant = Arm("conformant", name, None, f"403 {o.code} under a DECLARED pre_dispatch_layer — witness, not scored")
        res.witnesses["pre_dispatch_403"] = o.code
    elif o.status == 200 and entries is None:
        conformant = Arm("conformant", name, None, "200 with the handler index unreadable — could not rule out a catch-all; SKIP")
    else:
        conformant = Arm("conformant", name, False, f"{o.status} {o.code} — assertion (404 handler_not_found) does not hold")

    control = None
    if o.kind == "response":
        s.conn.send(s.signed(wire.request_id("registered"), "system/tree", "get"))
        t = s.read_response()
        res.witnesses["control"] = t.brief()
        if t.kind == "response":
            control = Arm("negative-control", "control", t.code != "handler_not_found", f"system/tree get: {t.status} {t.code or ''}".strip())
        else:
            control = Arm("negative-control", "control", None, f"could not look: {t.brief()}")
    s.conn.close()
    _finish(res, conformant, control)
    return res


# ── ECP-R57 — a root that is neither EXECUTE nor EXECUTE_RESPONSE closes the connection ───────────

def _await_close(s: wire.Session, bound: float) -> tuple[str, list[str]]:
    """Wait up to `bound` for a close. Returns (state, frames seen before it). state: close | open."""
    seen = []
    import time as _t
    deadline = _t.monotonic() + bound
    while True:
        left = deadline - _t.monotonic()
        if left <= 0:
            return "open", seen
        o = s.conn.read(left)
        if o.kind == "close":
            return "close", seen
        if o.kind == "timeout":
            return "open", seen
        seen.append(o.brief())


def check_r57(ctx: Ctx) -> Result:
    res = Result("ECP-R57", "connectivity/r57_invalid_root_type_closes", "ENTITY-CORE-PROTOCOL §3.3")
    s = _handshake(ctx, res)
    if s is None:
        return res
    res.witnesses["close_wait_bound_s"] = ctx.quiet_wait
    # Same builder and the same `included` for probe and control; only `root` differs (the file's control).
    included = dict(s.grant_included)
    included[s.me.peer_hash] = s.me.peer_entity
    s.conn.send(wire.frame(wire.envelope(s.me.peer_entity, included)))
    state, frames = _await_close(s, ctx.quiet_wait)
    if frames:
        res.witnesses["frame_before_close"] = frames
    name = "wrong-root-type"
    if state == "close":
        conformant = Arm("conformant", name, True, "closed" + (f" after {frames}" if frames else ""))
    else:
        s.conn.send(s.signed(wire.request_id("follow-up"), "system/tree", "get"))
        f = s.read_response(ctx.quiet_wait)
        res.witnesses["follow_up"] = f.brief()
        if f.kind == "response":
            conformant = Arm("conformant", name, False, f"the connection kept serving: follow-up answered {f.status} {f.code or ''}".strip())
        elif f.kind == "close":
            conformant = Arm("conformant", name, True, f"closed (observed on the follow-up, after {ctx.quiet_wait:g}s)")
        else:
            conformant = Arm("conformant", name, None, f"neither closed nor answered the follow-up: {f.brief()} — an outcome the file does not classify")
    s.conn.close()

    control = None
    c = _handshake(ctx, Result("", "", ""))
    if c is None:
        control = Arm("negative-control", "control", None, "could not look: second handshake failed")
    else:
        inc = dict(c.grant_included)
        inc[c.me.peer_hash] = c.me.peer_entity
        ex = wire.execute_entity(wire.request_id("valid-root"), "system/tree", "get", params=wire.tree_get_params(),
                                 author=c.me.peer_hash, capability=c.token_hash)
        sig = c.me.signature_entity(ex, c.sign_message)
        inc[sig["content_hash"]] = sig
        c.conn.send(wire.frame(wire.envelope(ex, inc)))
        t = c.read_response()
        res.witnesses["control"] = t.brief()
        if t.kind == "response":
            control = Arm("negative-control", "control", True, f"valid root answered {t.status} {t.code or ''}".strip())
        elif t.kind == "close":
            control = Arm("negative-control", "control", False, "closed on a VALID root: the probe's close is not about the root type")
        else:
            control = Arm("negative-control", "control", None, f"could not look: {t.brief()}")
        c.conn.close()
    _finish(res, conformant, control)
    return res


# ── UNALLOCATED-no-unsolicited-leg3-authenticate — §4.1 ────────────────────────────────────────

def check_no_leg3(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-no-unsolicited-leg3-authenticate"
    res = Result(rid, "connectivity/no_unsolicited_leg3_authenticate", "ENTITY-CORE-PROTOCOL §4.1")
    s = _handshake(ctx, res)
    if s is None:
        return res
    s.conn.send(s.signed(wire.request_id("first"), "system/tree", "get"))
    first = s.read_response()
    import time as _t
    res.witnesses["observation_window_ms"] = round((_t.monotonic() - s.leg2_at) * 1000, 1)
    res.witnesses["first"] = first.brief()
    in_window = [o for phase, o in s.unsolicited if phase == "session"]
    leg3 = [o for o in in_window if o.uri == wire.CONNECT and o.operation == "authenticate"]
    others = [o.detail for o in in_window if o not in leg3]
    if others:
        res.witnesses["other_inbound_executes"] = others
    before = [o.detail for phase, o in s.unsolicited if phase == "handshake"]
    if before:
        res.witnesses["inbound_before_leg2_response"] = before
    s.conn.close()
    if first.kind != "response":
        conformant = Arm("conformant", "no-leg-3", None, f"could not look: the first authenticated EXECUTE got {first.brief()}, so the window never closed")
    elif leg3:
        conformant = Arm("conformant", "no-leg-3", False, f"unsolicited leg-3 authenticate received: {[o.detail for o in leg3]}")
    else:
        conformant = Arm("conformant", "no-leg-3", True, f"no inbound connect/authenticate in {res.witnesses['observation_window_ms']} ms")
    control = None
    if first.kind == "response":
        control = Arm("negative-control", "control", first.status != 401, f"first authenticated EXECUTE answered {first.status} {first.code or ''}".strip())
    _finish(res, conformant, control)
    return res


# ── UNALLOCATED-key-type-mutual-verifiability — §4.5 ───────────────────────────────────────────

def _hello(ctx: Ctx, key_types: list[str] | None) -> tuple[wire.Outcome, wire.Conn | None]:
    try:
        c = wire.Conn(ctx.addr, ctx.timeout)
    except OSError as e:
        return wire.Outcome("close", detail=f"tcp_open: {e}"), None
    c.send(wire.frame(wire.hello_payload(Identity(), None, key_types)))
    return c.read(), c


def check_keytype(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-key-type-mutual-verifiability"
    res = Result(rid, "negotiation/keytype_accept_set_excludes_responder", "ENTITY-CORE-PROTOCOL §4.5")
    # The responder's own key_type, from its peer id (the file's "honest source"), via a plain hello.
    o, c = _hello(ctx, None)
    if c:
        c.close()
    r = wire.result_of(o) if o.kind == "response" and o.status == 200 else None
    pid = r.get("data", {}).get("peer_id") if isinstance(r, dict) and isinstance(r.get("data"), dict) else None
    try:
        kt = ident.parse_peer_id(pid)[0]
    except (ValueError, TypeError):
        res.message = f"could not look: responder key_type not derivable (plain hello: {o.brief()}, peer_id {pid!r})"
        return res
    own = ident.KEY_TYPE_NAMES.get(kt)
    if own is None:
        res.message = f"could not look: responder key_type {kt:#x} has no §1.5 string"
        return res
    excluded = next(n for k, n in sorted(ident.KEY_TYPE_NAMES.items()) if n != own)
    res.witnesses["responder_key_type"] = own
    res.witnesses["probe_key_types"] = [excluded]

    name = "refused"
    o, c = _hello(ctx, [excluded])
    res.witnesses["hello"] = o.brief()
    if o.kind == "response" and o.status == 400 and o.code == "unsupported_key_type":
        conformant = Arm("conformant", name, True, "400 unsupported_key_type at hello")
        res.witnesses["reject_surface"] = "hello"
    elif o.kind == "response" and o.status == 200:
        # Refused at hello by nobody. Drive authenticate to record where (if anywhere) it is refused.
        me = Identity()
        # a fresh hello on this same connection is not ours to send; re-run the whole handshake with the same key_types
        c.close()
        hs = wire.handshake(ctx.addr, me, ctx.timeout, ctx.sign_message, key_types=[excluded])
        if isinstance(hs, wire.HandshakeFailure):
            surf = f"{hs.step}: {hs.outcome.brief()}"
            res.witnesses["reject_surface"] = surf
            only_auth = hs.step == "authenticate" and hs.outcome.code == "unsupported_key_type"
            conformant = Arm("conformant", name, False,
                             ("400 unsupported_key_type ONLY at authenticate — §4.5 pins the reject at hello" if only_auth
                              else f"hello accepted; handshake then failed at {surf}"))
        else:
            hs.conn.close()
            res.witnesses["reject_surface"] = "none — handshake completed"
            conformant = Arm("conformant", name, False, "handshake completed with an accept-set excluding the responder's own key_type")
    elif o.kind == "response":
        conformant = Arm("conformant", name, None, f"hello refused {o.status} {o.code} — not the file's accept, not its refuse: unclassified")
        res.witnesses["unclassified"] = o.brief()
    else:
        conformant = Arm("conformant", name, None, f"no coded answer to the hello: {o.brief()} — unclassified")
    if c:
        c.close()

    t, c2 = _hello(ctx, [own])
    if c2:
        c2.close()
    res.witnesses["control"] = t.brief()
    if t.kind == "response":
        control = Arm("negative-control", "control", t.code != "unsupported_key_type", f"hello with key_types [{own!r}]: {t.status} {t.code or ''}".strip())
    else:
        control = Arm("negative-control", "control", None, f"could not look: {t.brief()}")
    _finish(res, conformant, control)
    return res


# ── UNALLOCATED-error-response-carries-code — §3.3 / §6.12 ─────────────────────────────────────

def error_shape(responses: list[wire.Outcome]) -> tuple[bool | None, bool | None, list[str]]:
    """(every error result is system/protocol/error, every error code is a text string, detail). None = no errors seen."""
    errs = [o for o in responses if o.kind == "response" and isinstance(o.status, int) and o.status >= 400]
    if not errs:
        return None, None, ["no error responses to judge"]
    types_ok = codes_ok = True
    detail = []
    for o in errs:
        r = wire.result_of(o)
        rtype = r.get("type") if isinstance(r, dict) else None
        data = r.get("data") if isinstance(r, dict) else None
        code = data.get("code") if isinstance(data, dict) else None
        if rtype != "system/protocol/error":
            types_ok = False
        if not isinstance(code, str):
            codes_ok = False
        detail.append(f"{o.status}: result {rtype!r}, code {code!r}")
    return types_ok, codes_ok, detail


def check_error_code(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-error-response-carries-code"
    res = Result(rid, "connectivity/error_response_carries_code", "ENTITY-CORE-PROTOCOL §3.3")
    s = _handshake(ctx, res)
    if s is None:
        return res
    inputs = [
        ("unregistered_local_path", s.signed(wire.request_id("e-404"), f"conformance-probe/unregistered/{os.urandom(6).hex()}", "get")),
        ("undefined_tree_operation", s.signed(wire.request_id("e-501"), "system/tree", "conformance-probe-undefined-op")),
        ("unauthenticated_tree_get", s.unauthenticated(wire.request_id("e-401"), "system/tree", "get")),
    ]
    responses, codes = [], {}
    for label, fr in inputs:
        s.conn.send(fr)
        o = s.read_response()
        codes[label] = o.brief()
        if o.kind != "response":
            break
        responses.append(o)
    s.conn.close()
    res.witnesses["codes_by_input"] = codes
    types_ok, codes_ok, detail = error_shape(responses)
    if types_ok is None:
        conformant = Arm("conformant", "coded-errors", None, "could not look: none of the three inputs produced an error response")
    else:
        conformant = Arm("conformant", "coded-errors", types_ok and codes_ok, "; ".join(detail))
    if len(responses) < len(inputs):
        res.witnesses["inputs_not_answered"] = [k for k, _ in inputs][len(responses):]

    # Control, suite-side: both assertions must reject the absent-code shapes.
    fx1 = wire.Outcome("response", status=404, envelope={"root": {"type": wire.RESPONSE, "data": {"request_id": "f1", "status": 404}}})
    fx2 = wire.Outcome("response", status=404, envelope={"root": {"type": wire.RESPONSE, "data": {"request_id": "f2", "status": 404,
                       "result": {"type": "system/protocol/error", "data": {"message": "no code here"}}}}})
    t1, _, _ = error_shape([fx1])
    _, c2, _ = error_shape([fx2])
    control = Arm("negative-control", "control", t1 is False and c2 is False,
                  f"fixture without result: type assertion {'refused' if t1 is False else 'PASSED'}; fixture without code: code assertion {'refused' if c2 is False else 'PASSED'}")
    _finish(res, conformant, control)
    return res


CHECKS = {
    "ECP-R1": check_r1,
    "ECP-R6": check_r6,
    "ECP-R9": check_r9,
    "ECP-R44": check_r44,
    "ECP-R45": check_r45,
    "ECP-R57": check_r57,
    "UNALLOCATED-no-unsolicited-leg3-authenticate": check_no_leg3,
    "UNALLOCATED-key-type-mutual-verifiability": check_keytype,
    "UNALLOCATED-error-response-carries-code": check_error_code,
}

# The reference oracle's check each requirement file names — provenance only, for a consumer's category filter.
CATEGORY = {rid: "connectivity" for rid in CHECKS} | {"UNALLOCATED-key-type-mutual-verifiability": "negotiation"}


def run(rid: str, ctx: Ctx) -> Result:
    try:
        return CHECKS[rid](ctx)
    except Exception as e:  # a suite defect is never a peer verdict
        return Result(rid, "suite-error", "", "SKIP",
                      f"SUITE DEFECT (not a peer result): {e.__class__.__name__}: {e}",
                      witnesses={"traceback": traceback.format_exc(limit=6)}, peer_attributable=False)
