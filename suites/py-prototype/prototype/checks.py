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

from . import cbor, emitted, ident, wire
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
    # Set by a check for which "the peer stopped accepting connections" IS the observation (ECP-R66-pending-c). Everywhere
    # else a connection that could not be opened makes the verdict could-not-look (F57).
    unreachable_is_observation: bool = False


@dataclass
class Ctx:
    addr: str
    timeout: float
    sign_message: str
    pre_dispatch_layer: bool
    quiet_wait: float  # how long "no response" is waited for, in the arms that accept it
    declared_max_payload: int | None = None  # §4.10(a)'s configured bound, from the posture; None = undeclared


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
    # The unregistered-path request names an UNDEFINED operation, not `get`: three Keystone peers serve `get` on every
    # path through a hidden tree fallback (F53), and a request_id check must not score ECP-R45's defect as could-not-look.
    # The file fixes the path, not the operation.
    op_for = {"unregistered": "conformance-probe-undefined-op"}
    err = s.conn.send(b"".join(s.signed(rid, uri, op_for.get(cls, "get"), resource=r) for rid, uri, r, cls in plan))
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

    # WITNESS, never scored: the same probe WITH a resource. The file does not say whether the probe carries one, and
    # instruments that chose differently got different answers from the same peer (F52). Recording both arms of that
    # unpinned input is how the requirement gets pinned.
    if o.kind == "response":
        s.conn.send(s.signed(wire.request_id("undefined-op-res"), "system/tree", "conformance-probe-undefined-op",
                             resource={"targets": ["system/type/"]}))
        w = s.read_response()
        res.witnesses["probe_with_resource"] = w.brief()
        if w.kind != "response":
            o = w  # the connection is gone; the control below must not run on it

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

    # WITNESSES, never scored: other members of the same input domain. §3.3's row covers ANY unregistered path on the
    # local peer; the file pins one shape and the reference oracle probes another, and peers answer them differently
    # (F52). Each variant changes one input: resource presence, URI form, namespace.
    rpid = s.responder_hello.get("peer_id") if isinstance(s.responder_hello, dict) else None
    sys_path = f"system/no-such-handler-cnf-{os.urandom(4).hex()}"
    variants = [("with_resource", probe, {"targets": [probe]}),
                ("system_namespace_with_resource", sys_path, {"targets": [sys_path]}),
                ("system_namespace_no_resource", sys_path, None),
                ("undefined_operation_with_resource", probe, {"targets": [probe]}),
                ("undefined_operation_no_resource", probe, None)]
    if isinstance(rpid, str):
        variants.append(("fully_qualified_with_resource", f"entity://{rpid}/{probe}", {"targets": [probe]}))
    domain = {}
    for label, uri, resource in variants:
        if o.kind != "response":
            break
        op = "conformance-probe-undefined-op" if label.startswith("undefined_operation") else "get"
        s.conn.send(s.signed(wire.request_id("unregistered-" + label), uri, op, resource=resource))
        w = s.read_response()
        domain[label] = w.brief()
        if w.kind != "response":
            o = w
    res.witnesses["domain_variants"] = domain

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


# ── ECP-R57 — a root that is neither EXECUTE nor EXECUTE_RESPONSE is answered 400 invalid_request ──
#
# ⛔⛔ THE OBLIGATION INVERTED AT 0.8.2.25 AND THIS CODE MEASURED THE OLD ONE UNTIL 2026-09-16 (F75).
# Under .21 §9.1's row and §3.3's body both said *"close connection"*, and this check scored
# conformant on `state == "close"` — it watched the socket. Under .25 §3.3 says the peer MUST answer
# `400 invalid_request` before closing and **the close itself remains the peer's choice**, with
# §4.11 as the normative home. `close` and `coded frame` SWAPPED PLACES.
#
# ⚠ THE PART WORTH READING TWICE: the requirement file and the item were re-authored to .25 on
# 2026-09-15 (b) and THIS FUNCTION WAS NOT. `make check` stayed green, `IMPLEMENTS` still listed
# ECP-R57, and the executed-by-a-suite ratchet still counted it — because every one of those
# measures a DECLARATION. A run taken in that window would have re-produced the void 34-of-37
# result against a rule that no longer exists. See AP-18.

# `_await_close` lived here and is DELETED, not kept "in case": it waited for a socket close and
# reported the frames seen before it, which is precisely the .21 instrument — the shape whose
# obligation inverted. Keeping it would leave the old measurement one call away.


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
    name = "wrong-root-type"
    # ⭐ THE READ IS NOW FOR A RESPONSE, NOT FOR A CLOSE. Under .25 the coded frame IS the obligation
    # and the close is discretionary, so a peer that answers and then closes is conformant, and the
    # follow-up probe that .21's arms were built around no longer decides this row at all.
    o = s.read_response(ctx.quiet_wait)
    res.witnesses["status_and_code"] = o.brief()
    conformant, klass = _preadmission(name, o, 400, "invalid_request",
                                      admitted_detail="the wrong-root frame was admitted")
    res.witnesses["preadmission_class"] = klass
    if klass == "silent_drop":
        # ⚠ ONE INPUT CHANGED, to tell a peer that DROPPED the frame and kept serving from one that
        # wedged. Both are `silent_drop` under §4.11 and both FAIL — this does not rescue the
        # verdict, it attributes it. F61 measured 21 peers in this class when it was unscoreable.
        s.conn.send(s.signed(wire.request_id("follow-up"), "system/tree", "get"))
        f = s.read_response(ctx.quiet_wait)
        res.witnesses["follow_up_after_silence"] = f.brief()
        conformant = Arm("conformant", name, False, conformant.outcome +
                         f"; then a correct request on the same connection: {f.brief()}")
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
        if t.kind == "response" and (t.status, t.code) == (400, "invalid_request"):
            # ⛔ THE CONTROL'S OWN REFUSE ARM, and it was missing until 2026-09-16: the item refuses
            # exactly this outcome. A peer that answers `400 invalid_request` to a VALID root is
            # refusing the envelope construction, not the root type — so the probe's identical answer
            # measures nothing, and reporting PASS would be the vacuity the control exists to catch.
            control = Arm("negative-control", "control", False,
                          "a VALID root was answered 400 invalid_request — the probe's refusal is not "
                          "attributable to the root type; unscoreable, not passed")
        elif t.kind == "response":
            control = Arm("negative-control", "control", True, f"valid root answered {t.status} {t.code or ''}".strip())
        elif t.kind == "close":
            control = Arm("negative-control", "control", False, "closed on a VALID root: the probe's refusal is not about the root type")
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

def _hello(ctx: Ctx, key_types: list[str] | None, **fields) -> tuple[wire.Outcome, wire.Conn | None]:
    try:
        c = wire.Conn(ctx.addr, ctx.timeout)
    except OSError as e:
        return wire.Outcome("unreachable", detail=f"tcp_open: {e}"), None
    c.send(wire.frame(wire.hello_payload(Identity(), None, key_types, **fields)))
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


# ── §4.5 hello refusals: ECP-R47, ECP-R47-pending-b, UNALLOCATED-hash-format-intersection ────────

def _one_hello(ctx: Ctx, **fields) -> wire.Outcome:
    o, c = _hello(ctx, None, **fields)
    if c:
        c.close()
    return o


def _coded_refusal(name: str, o: wire.Outcome, status: int, code: str) -> Arm:
    """The file asserts status AND decoded code. Every other outcome is that assertion not holding — including a close
    or a timeout, because §4.7 requires the coded EXECUTE_RESPONSE before any close."""
    if o.kind == "response" and o.status == status and o.code == code:
        return Arm("conformant", name, True, f"{status} {code}")
    if o.kind == "response":
        return Arm("conformant", name, False, f"{o.status} {o.code or '-'} — assertion ({status} {code}) does not hold")
    return Arm("conformant", name, False, f"no coded answer: {o.brief()} — §4.7 requires the coded response before a close")


# ── §4.11 pre-admission refusals (0.8.2.25) ───────────────────────────────────────────────────────
#
# ⛔ THE ONE RULE THIS HELPER EXISTS TO KEEP: the two failures are SCORED SEPARATELY.
# §4.11: *"Two behaviours are non-conformant, and they are distinct failures rather than one"* —
# dropping the frame (the caller learns nothing until its own §6.11(c) deadline) and closing with no
# coded frame (indistinguishable from a network fault; on a multiplexed connection it destroys
# unrelated admitted requests). **Collapsing them lets a peer get credit for the wrong fix**, and
# arch said so in terms when ruling CQ-34/CQ-35. `_coded_refusal` collapses every non-conformant
# shape into one string, which is why this is a separate helper rather than a flag on that one.
#
# ⚠ THE CODE BELONGS TO THE CAUSE, NOT TO THE CLASS `[MUST]` (§4.11). A wrong code is its own
# failure class: *"a single code for the class would answer an honest caller under the wrong reason
# and send them to the wrong layer."*
PREADMISSION = ("coded_conformant", "coded_response_wrong_code", "bare_close", "silent_drop",
                "admitted", "could_not_look")


def _preadmission(name: str, o: wire.Outcome, status: int, code: str,
                  admitted_detail: str = "the frame was processed rather than refused") -> tuple[Arm, str]:
    """Score one pre-admission refusal against §4.11. Returns (Arm, failure class) — the class is
    recorded as a witness so triage separates a drop from a bare close from a wrong code."""
    if o.kind == "response" and o.status == status and o.code == code:
        return Arm("conformant", name, True, f"{status} {code} coded frame"), "coded_conformant"
    if o.kind == "response" and o.status == 200:
        return Arm("conformant", name, False, f"{admitted_detail} (200)"), "admitted"
    if o.kind == "response":
        return (Arm("conformant", name, False,
                    f"coded {o.status} {o.code or '-'} — §4.11 pins ({status} {code}) for this cause; "
                    f"the code selects the caller's remedy, so a code merely in the right family is "
                    f"still wrong"), "coded_response_wrong_code")
    if o.kind == "close":
        return (Arm("conformant", name, False,
                    f"bare close, no coded frame ({o.detail or 'no detail'}) — §4.11's SECOND named "
                    f"failure, indistinguishable from a network fault (§4.6)"), "bare_close")
    if o.kind == "timeout":
        return (Arm("conformant", name, False,
                    f"silent drop, no response and no close ({o.detail or 'no detail'}) — §4.11's "
                    f"FIRST named failure; the caller learns nothing until its own §6.11(c) deadline"),
                "silent_drop")
    return Arm("conformant", name, None, f"could not look: {o.brief()}"), "could_not_look"


def _not_code_control(o: wire.Outcome, code: str, label: str) -> Arm:
    if o.kind != "response":
        return Arm("negative-control", "control", None, f"could not look: {label}: {o.brief()}")
    return Arm("negative-control", "control", o.code != code, f"{label}: {o.status} {o.code or '-'}")


def _finish_arms(res: Result, conformant: list[Arm], control: Arm | None):
    """Several conformant arms, one control (a file that names two inputs for one obligation). Any arm refused is FAIL;
    any arm that could not be evaluated, with none refused, is SKIP; otherwise the control decides as in _finish."""
    held = [a.held for a in conformant]
    merged = Arm("conformant", "+".join(a.name for a in conformant),
                 False if False in held else None if None in held else True,
                 " | ".join(f"{a.name}: {a.outcome}" for a in conformant))
    _finish(res, merged, control)
    res.arms = conformant + ([control] if control else [])


def check_r47(ctx: Ctx) -> Result:
    res = Result("ECP-R47", "connectivity/r47_incompatible_protocol", "ENTITY-CORE-PROTOCOL §4.5")
    o = _one_hello(ctx, protocols=["x-conformance-probe/0"])
    res.witnesses["disjoint"] = o.brief()
    conformant = _coded_refusal("refused", o, 400, "incompatible_protocol")
    t = _one_hello(ctx, protocols=[wire.PROTOCOL_VERSION])
    res.witnesses["intersecting"] = t.brief()
    _finish(res, conformant, _not_code_control(t, "incompatible_protocol", f"protocols [{wire.PROTOCOL_VERSION!r}]"))
    return res


def check_r47b(ctx: Ctx) -> Result:
    res = Result("ECP-R47-pending-b", "connectivity/r47b_absent_or_empty_protocols", "ENTITY-CORE-PROTOCOL §4.5")
    a = _one_hello(ctx, protocols=wire.ABSENT)
    e = _one_hello(ctx, protocols=[])
    res.witnesses["absent"] = a.brief()
    res.witnesses["empty"] = e.brief()
    arms = [_coded_refusal("absent", a, 400, "invalid_request"), _coded_refusal("empty", e, 400, "invalid_request")]
    t = _one_hello(ctx, protocols=[wire.PROTOCOL_VERSION])
    res.witnesses["present"] = t.brief()
    _finish_arms(res, arms, _not_code_control(t, "invalid_request", f"protocols [{wire.PROTOCOL_VERSION!r}]"))
    return res


HASH_FORMAT_PROBE = "ecfv1-conformance-probe"  # DECLARED unallocated in §1.2 at entity-core-protocol/v0.8.2.21; re-check at each re-take


def check_hash_format_intersection(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-hash-format-intersection"
    res = Result(rid, "negotiation/hash_formats_disjoint_refused", "ENTITY-CORE-PROTOCOL §4.5")
    o = _one_hello(ctx, hash_formats=[HASH_FORMAT_PROBE])
    res.witnesses["disjoint"] = o.brief()
    res.witnesses["probe_value"] = HASH_FORMAT_PROBE
    conformant = _coded_refusal("refused", o, 400, "incompatible_hash_format")
    t = _one_hello(ctx, hash_formats=["ecfv1-sha256"])
    res.witnesses["intersecting"] = t.brief()
    # WITNESS, never scored: `hash_formats` absent. The file's reading says absence is the floor default, not an empty
    # intersection — recorded so a peer that confuses the two is visible without this file inventing an arm for it.
    w = _one_hello(ctx)
    res.witnesses["absent_hash_formats"] = w.brief()
    _finish(res, conformant, _not_code_control(t, "incompatible_hash_format", "hash_formats ['ecfv1-sha256']"))
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


# ── encoding, emitted side: ECP-R2, ECP-R12, ECP-R7-pending-b and three UNALLOCATED rows ─────────
#
# One capture per requirement — a handshake (hello and authenticate responses) and one request answered with an error —
# then a predicate from emitted.py over what was received. Each negative control runs the SAME predicate over fixtures the
# suite builds, which must fail: no conformant peer can be made to emit a wrong hash, so the control is suite-side.

def _capture(ctx: Ctx, res: Result) -> list[tuple[str, wire.Outcome]] | None:
    s = _handshake(ctx, res)
    if s is None:
        return None
    frames = list(s.received)
    # The file's 4xx member (UNALLOCATED-emitted-frames-are-canonical-ecf): an unregistered path, `get`.
    s.conn.send(s.signed(wire.request_id("emit-4xx"), "x-conformance-probe/unregistered", "get"))
    frames.append(("4xx response", s.read_response()))
    s.conn.close()
    res.witnesses["captured"] = [f"{label}: {o.brief()}" for label, o in frames]
    return frames


def _fixture_env(me: Identity | None = None, **token_overrides) -> dict:
    """A self-consistent authenticate-shaped response the suite authors: a grant result, the token, its signature and the
    granter's peer entity in `included`, every hash correct. Fixtures are this with ONE thing broken."""
    me = me or Identity(bytes(32))
    grantee = Identity(bytes([1]) * 32)
    token_data = {"grants": [{"handlers": {"include": ["system/tree"]}, "resources": {"include": ["system/type/*"]},
                              "operations": {"include": ["get"]}}],
                  "granter": me.peer_hash, "grantee": grantee.peer_hash, "created_at": 1789300000000}
    token_data.update(token_overrides)
    token = ident.entity("system/capability/token", token_data)
    sig = me.signature_entity(token)
    result = ident.entity("system/capability/grant", {"token": token["content_hash"]})
    root = ident.entity(wire.RESPONSE, {"request_id": "fixture", "status": 200, "result": result})
    inc = {e["content_hash"]: e for e in (token, sig, me.peer_entity)}
    return {"root": root, "included": inc}


def _with(env: dict, path: tuple, value: object) -> dict:
    """A deep copy of env with one value replaced (no hash recomputed — the point of most fixtures)."""
    import copy
    out = copy.deepcopy(env)
    cur = out
    for k in path[:-1]:
        cur = cur[k]
    cur[path[-1]] = value
    return out


def _emitted(ctx: Ctx, res: Result, arm: str, predicate, must_fail: list, must_pass: list = (), should: bool = False) -> Result:
    frames = _capture(ctx, res)
    if frames is None:
        return res
    envs = [o.envelope for _, o in frames if o.envelope is not None]
    unreadable = [f"{label}: {o.brief()}" for label, o in frames if o.envelope is None]
    if unreadable:
        res.witnesses["frames_not_decoded"] = unreadable
    held, detail, w = predicate(envs)
    res.witnesses.update(w)
    conformant = Arm("conformant", arm, held, detail if held is not None else f"could not look: {detail}")
    if held is False and should:
        conformant.outcome = f"SHOULD not met: {detail}"
    refused = [label for label, env in must_fail if predicate([env])[0] is not False]
    accepted = [label for label, env in must_pass if predicate([env])[0] is not True]
    control = Arm("negative-control", "control", not refused and not accepted,
                  f"{len(must_fail)} fixture(s) refused" + (f", {len(must_pass)} accepted" if must_pass else "")
                  if not refused and not accepted else f"fixtures NOT refused: {refused}; NOT accepted: {accepted}")
    _finish(res, conformant, control)
    if should and res.verdict == "FAIL":
        res.verdict = "WARN"
    return res


def check_r2(ctx: Ctx) -> Result:
    res = Result("ECP-R2", "encoding/r2_emitted_content_hash_recomputes", "ENTITY-CORE-PROTOCOL §1.2, §1.3, §7.1")
    good = _fixture_env()
    tok_key = next(k for k, e in good["included"].items() if e["type"] == "system/capability/token")
    tok = good["included"][tok_key]
    flipped = tok["content_hash"][:-1] + bytes([tok["content_hash"][-1] ^ 1])
    over_all = ident.varint(0) + emitted.DIGESTS[0][0](cbor.encode({"type": tok["type"], "data": tok["data"], "content_hash": tok["content_hash"]})).digest()
    unordered = ident.entity("test/v1", {"z": 1, "a": 2})
    # {type, data} with data's keys in insertion order "z" before "a" — the non-deterministic encoder this row catches.
    raw = b"\xa2" + cbor.encode("data") + b"\xa2" + cbor.encode("z") + cbor.encode(1) + cbor.encode("a") + cbor.encode(2) + cbor.encode("type") + cbor.encode("test/v1")
    unordered["content_hash"] = ident.varint(0) + emitted.DIGESTS[0][0](raw).digest()
    fixtures = [("flipped digest byte", _with(good, ("included", tok_key, "content_hash"), flipped)),
                ("content_hash inside the hash input", _with(good, ("included", tok_key, "content_hash"), over_all)),
                ("insertion-order key encoding", {"root": unordered, "included": {}})]
    return _emitted(ctx, res, "recomputes", emitted.all_hashes_recompute, fixtures, [("the unbroken fixture", good)])


def check_r12(ctx: Ctx) -> Result:
    res = Result("ECP-R12", "encoding/r12_emitted_hashes_flat_bstr", "ENTITY-CORE-PROTOCOL §1.2, §2.5")
    good = _fixture_env()
    ch = good["root"]["content_hash"]
    fixtures = [("display-form text", _with(good, ("root", "content_hash"), "ecfv1-sha256:" + ch[1:].hex())),
                ("tag 37 around the correct bytes", _with(good, ("root", "content_hash"), cbor.Tag(37, ch))),
                ("array [code, digest]", _with(good, ("root", "content_hash"), [0, ch[1:]])),
                ("code 0x00 with a 31-byte digest", _with(good, ("root", "content_hash"), ch[:-1]))]
    return _emitted(ctx, res, "flat-bstr", emitted.all_hashes_flat, fixtures, [("the unbroken fixture", good)])


def check_r7b(ctx: Ctx) -> Result:
    res = Result("ECP-R7-pending-b", "encoding/r7b_included_keys_equal_content_hash", "ENTITY-CORE-PROTOCOL §3.1")
    good = _fixture_env()
    keys = list(good["included"])
    hexed = dict(good, included={k.hex(): e for k, e in good["included"].items()})
    swapped = dict(good, included={keys[0]: good["included"][keys[1]], keys[1]: good["included"][keys[0]],
                                   **{k: good["included"][k] for k in keys[2:]}})
    return _emitted(ctx, res, "keys-match", emitted.included_keys_match,
                    [("keyed by lowercase hex text", hexed), ("two entries' keys swapped", swapped)], [("the unbroken fixture", good)])


def check_frames_canonical(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-emitted-frames-are-canonical-ecf"
    res = Result(rid, "encoding/emitted_frames_reencode_identically", "ENTITY-CORE-PROTOCOL §1.11; ENTITY-CBOR-ENCODING §5.2")
    frames = _capture(ctx, res)
    if frames is None:
        return res
    per, bad = {}, []
    for label, o in frames:
        if o.raw is None:
            per[label] = f"no payload: {o.brief()}"
            continue
        ok, why = emitted.frame_is_canonical(o.raw)
        per[label] = why
        if not ok:
            bad.append(f"{label}: {why}")
    res.witnesses["per_frame"] = per
    n = sum(1 for _, o in frames if o.raw is not None)
    conformant = Arm("conformant", "canonical", (not bad) if n else None,
                     ("; ".join(bad) if bad else f"{n} frame payloads re-encode identically") if n else "could not look: no frame payload captured")
    # Control: three value-equal, byte-different serializations of one canonical response.
    base = {"root": ident.entity(wire.RESPONSE, {"request_id": "fixture", "status": 404, "cnf_one": 1,
                                                 "result": ident.entity("system/protocol/error", {"code": "handler_not_found"})}),
            "included": {}}
    canon = cbor.encode(base)
    root_bytes = cbor.encode(base["root"])
    swapped = b"\xa2" + cbor.encode("included") + cbor.encode({}) + cbor.encode("root") + root_bytes
    one = cbor.encode("cnf_one") + b"\x01"
    long_int = canon.replace(one, cbor.encode("cnf_one") + b"\x18\x01", 1)
    indefinite = b"\xa2" + cbor.encode("root") + root_bytes + cbor.encode("included") + b"\xbf\xff"
    fixtures = {"root/included swapped": swapped, "integer 1 as 18 01": long_int, "indefinite-length included map": indefinite}
    wrong = [k for k, b in fixtures.items() if b == canon or emitted.frame_is_canonical(b)[0]]
    ok_canon = emitted.frame_is_canonical(canon)[0]
    control = Arm("negative-control", "control", not wrong and ok_canon,
                  "3 fixture payloads refused, the canonical one accepted" if not wrong and ok_canon
                  else f"NOT refused: {wrong}; canonical accepted: {ok_canon}")
    _finish(res, conformant, control)
    return res


def check_typed_fields(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-emitted-entities-conform-to-protocol-types"
    res = Result(rid, "encoding/emitted_typed_fields", "ENTITY-CORE-PROTOCOL §3.5, §3.6")
    me = Identity(bytes(32))
    good = _fixture_env(me)
    sig_key = next(k for k, e in good["included"].items() if e["type"] == "system/signature")
    tok_key = next(k for k, e in good["included"].items() if e["type"] == "system/capability/token")
    fixtures = [("signer is the Base58 peer id", _with(good, ("included", sig_key, "data", "signer"), me.peer_id)),
                ("delegation_caveats is an array", _with(good, ("included", tok_key, "data", "delegation_caveats"), [True, 3, 0])),
                ("max_delegation_depth is the text \"3\"", _with(good, ("included", tok_key, "data", "delegation_caveats"), {"max_delegation_depth": "3"}))]
    open_typed = _with(good, ("included", tok_key, "data", "delegation_caveats"), {"max_delegation_depth": 3, "x_future": 1})
    return _emitted(ctx, res, "typed", emitted.typed_fields, fixtures, [("caveats with an extra key and correct declared types", open_typed)])


def check_optional_nulls(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-emitted-optional-fields-absent-not-null"
    res = Result(rid, "encoding/emitted_optional_fields_absent_not_null", "ENTITY-CORE-PROTOCOL §1.3")
    null_fixture = _fixture_env(expires_at=None)
    zero_fixture = _fixture_env(delegation_caveats={"max_delegation_depth": 0})
    return _emitted(ctx, res, "absent-not-null", emitted.optional_nulls, [("token with expires_at: null", null_fixture)],
                    [("token with max_delegation_depth: 0", zero_fixture)], should=True)


# ── encoding, receiving side: hellos carrying one defect each ──────────────────────────────────────
#
# The hello is the surface: §4.2 puts it before any grant, so no posture can be the cause of a refusal. Each probe and its
# control come from wire.hello_probe and differ in the one thing the requirement is about.

def _raw_hello(ctx: Ctx, framed: bytes) -> wire.Outcome:
    try:
        c = wire.Conn(ctx.addr, ctx.timeout)
    except OSError as e:
        return wire.Outcome("unreachable", detail=f"tcp_open: {e}")
    err = c.send(framed)
    o = wire.Outcome("close", detail=err) if err else c.read()
    if o.kind == "timeout":
        # WITNESS, never scored (F61): silence is neither of a refusal file's arms. One input changed — a correct hello on
        # the SAME connection — tells a peer that dropped the frame and kept serving from one that wedged.
        c.send(wire.frame(wire.hello_payload(Identity())))
        after = c.read()
        o.detail += f"; then a correct hello on the same connection: {after.brief().split(' (request_id')[0]}"
    c.close()
    return o


def _refused_any(name: str, o: wire.Outcome) -> Arm:
    """For rows that require REJECTION and pin no code: a non-200 response or a close is refusal; a 200 is the failure."""
    if o.kind == "response" and o.status == 200:
        return Arm("conformant", name, False, "answered as a hello (200) — the input was processed")
    if o.kind == "response":
        return Arm("conformant", name, True, f"refused {o.status} {o.code or '-'}")
    if o.kind == "close":
        return Arm("conformant", name, True, f"refused by close ({o.detail})")
    return Arm("conformant", name, None, f"{o.brief()} — neither answered nor refused; the file's arms do not classify it")


def _hello_answered_control(o: wire.Outcome) -> Arm:
    if o.kind == "response" and o.status == 200:
        return Arm("negative-control", "control", True, "the control hello was answered (200)")
    if o.kind == "close":
        return Arm("negative-control", "control", False, f"the control hello was closed ({o.detail}) — the probe's refusal proves nothing")
    return Arm("negative-control", "control", None, f"control outcome {o.brief()} is neither of the file's arms — unscoreable, not passed")


def check_r3(ctx: Ctx) -> Result:
    res = Result("ECP-R3", "encoding/r3_root_hash_mismatch_not_processed", "ENTITY-CORE-PROTOCOL §1.8, §7.2, §6.5")
    res.witnesses["close_wait_bound_s"] = ctx.timeout
    o = _raw_hello(ctx, wire.hello_probe(Identity(), corrupt_root=True))
    res.witnesses["status_and_code"] = o.brief()
    conformant = _refused_any("root-hash-mismatch", o)
    # WITNESS-ONLY (F24): §3.4 lets params validation be deferred, so either outcome is conformant today.
    res.witnesses["params_hash_mismatch"] = _raw_hello(ctx, wire.hello_probe(Identity(), corrupt_params=True)).brief()
    t = _raw_hello(ctx, wire.hello_probe(Identity()))
    res.witnesses["control"] = t.brief()
    _finish(res, conformant, _hello_answered_control(t))
    return res


def check_r7(ctx: Ctx) -> Result:
    """⛔ RE-AUTHORED TO 0.8.2.25, 2026-09-16. This scored `_refused_any` — *any* non-200 counts —
    which is the 0.8.2.21 behaviour, and it survived the file's own .24 re-authoring untouched.

    .24 PINNED the code (§5.2a corollary 1: `400 hash_mismatch`) and declared `400 non_canonical_ecf`
    non-conformant here IN TERMS. `_refused_any` scores both as conformant. ⇒ The file predicted that
    a block of peers would FAIL under the pin *with no peer having changed a line*, and the
    instrument could not have produced that result: it passes every peer the prediction is about.
    **A prediction whose instrument cannot falsify it is not a prediction.**

    .25 adds §4.11: the drop and the bare close are non-conformant and SCORED SEPARATELY (CQ-34,
    CQ-35 ruled), so this file's three `inconclusive` arms collapse to two distinct failure classes
    plus a wrong-code class. See AP-18 for how the drift went unnoticed.
    """
    res = Result("ECP-R7", "encoding/r7_unused_included_hash_mismatch_not_processed",
                 "ENTITY-CORE-PROTOCOL §3.1, §1.8, §4.11, §5.2a, §6.5")
    good = ident.entity("primitive/any", {"x": 1})
    bad = dict(good, data={"x": 2})  # key and carried hash still agree with each other: not ECP-R7-pending-b's defect
    o = _raw_hello(ctx, wire.hello_probe(Identity(), included={bad["content_hash"]: bad}))
    res.witnesses["status_and_code"] = o.brief()
    # §4.11's cause table, row 3: resolution integrity -> 400 hash_mismatch, stated at §5.2a.
    conformant, klass = _preadmission("unused-included-mismatch", o, 400, "hash_mismatch",
                                      admitted_detail="answered as a hello — the envelope was "
                                                      "processed with an unvalidated included entity")
    res.witnesses["preadmission_class"] = klass
    t = _raw_hello(ctx, wire.hello_probe(Identity(), included={good["content_hash"]: good}))
    res.witnesses["control"] = t.brief()
    control = _hello_answered_control(t)
    if t.kind == "response" and t.status != 200:
        res.witnesses["outcome_if_coded_refusal"] = t.brief()
    _finish(res, conformant, control)
    return res


TAG_MEMBERS = [  # (member, probe extra pairs or None, control extra pairs, included-entity data or None, wrap)
    ("tag 0 on a top-level hello data field", (("x_cnf_probe", cbor.Tag(0, "2026-09-13T00:00:00Z")),), (("x_cnf_probe", "2026-09-13T00:00:00Z"),), None, None),
    ("tag 1 on a top-level hello data field", (("x_cnf_probe", cbor.Tag(1, 1713350272)),), (("x_cnf_probe", 1713350272),), None, None),
    ("tag 37 on a bstr in hello data", (("x_cnf_probe", cbor.Tag(37, bytes(range(16)))),), (("x_cnf_probe", bytes(range(16))),), None, None),
    ("tag 32 on a tstr in hello data", (("x_cnf_probe", cbor.Tag(32, "https://example.invalid/")),), (("x_cnf_probe", "https://example.invalid/"),), None, None),
    ("tag 1 inside an array inside a nested map", (("x_cnf_probe", {"inner": [cbor.Tag(1, 1)]}),), (("x_cnf_probe", {"inner": [1]}),), None, None),
    ("tag 0 inside an included entity's data", (), (), {"t": cbor.Tag(0, "2026-09-13T00:00:00Z")}, None),
    ("tag 55799 wrapping the whole frame payload", (), (), None, 55799),
]


def _tag_hello(extra: tuple, inc_data: object, wrap: int | None) -> bytes:
    included = None
    if inc_data is not None:
        e = wire.probe_entity("primitive/any", inc_data)
        included = {e["content_hash"]: e}
    return wire.hello_probe(Identity(), extra=extra, included=included, wrap_tag=wrap)


def _untag(v: object) -> object:
    if isinstance(v, cbor.Tag):
        return _untag(v.value)
    if isinstance(v, dict):
        return {k: _untag(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_untag(x) for x in v]
    return v


def check_cbor_tag(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-cbor-tag-rejected"
    res = Result(rid, "encoding/cbor_tag_in_data_refused_non_canonical_ecf", "ENTITY-CBOR-ENCODING §6.3")
    arms, controls, members = [], [], {}
    for member, extra, control_extra, inc_data, wrap in TAG_MEMBERS:
        o = _raw_hello(ctx, _tag_hello(extra, inc_data, wrap))
        t = _raw_hello(ctx, _tag_hello(control_extra, _untag(inc_data) if inc_data is not None else None, None))
        members[member] = {"probe": o.brief(), "control": t.brief()}
        if o.kind == "response" and o.status == 400 and o.code == "non_canonical_ecf":
            arms.append(Arm("conformant", member, True, "400 non_canonical_ecf"))
        elif wrap is not None and o.kind == "close":
            arms.append(Arm("conformant", member, True, f"close ({o.detail}) — accepted for the whole-payload member only"))
        elif o.kind in ("response", "close"):
            arms.append(Arm("conformant", member, False, f"{o.brief()} — assertion (400 non_canonical_ecf) does not hold"))
        else:
            arms.append(Arm("conformant", member, None, f"{o.brief()} — unclassified"))
        controls.append(t.code != "non_canonical_ecf" if t.kind == "response" else None)
    res.witnesses["members"] = members
    held = [c for c in controls]
    control = Arm("negative-control", "control", False if False in held else None if None in held else True,
                  f"untagged twins: {sum(1 for c in held if c)} of {len(held)} not refused non_canonical_ecf")
    _finish_arms(res, arms, control)
    return res


DUP_MEMBERS = [
    ("top-level hello data map, identical values", (("x_cnf_dup", 1), ("x_cnf_dup", 1))),
    ("top-level hello data map, differing values (1 then 2)", (("x_cnf_dup", 1), ("x_cnf_dup", 2))),
    ("a map nested inside hello data", (("x_cnf_probe", cbor.Pairs((("x_cnf_dup", 1), ("x_cnf_dup", 1)))),)),
]


def check_dup_key(ctx: Ctx) -> Result:
    rid = "UNALLOCATED-duplicate-map-key-rejected"
    res = Result(rid, "encoding/duplicate_map_key_not_processed", "ENTITY-CBOR-ENCODING §4.1 Rule 5, §9.2")
    arms, codes = [], {}
    for member, extra in DUP_MEMBERS:
        o = _raw_hello(ctx, wire.hello_probe(Identity(), extra=extra))
        codes[member] = o.brief()
        arms.append(_refused_any(member, o))
    res.witnesses["status_and_code"] = codes
    t = _raw_hello(ctx, wire.hello_probe(Identity(), extra=(("x_cnf_dup", 1),)))
    res.witnesses["control"] = t.brief()
    _finish_arms(res, arms, _hello_answered_control(t))
    return res


def _outcome_class(o: wire.Outcome) -> tuple:
    return (o.kind, o.status, o.code) if o.kind == "response" else (o.kind,)


def _r4b_put_member(ctx: Ctx, res: Result) -> Arm:
    """The file's third member: a put of an entity carrying a null optional, answered as the same put without it. Needs
    `system/tree: put`; without it the member is UNMEASURABLE under that posture (a 403), never scored."""
    member = "tree:put entity {type: \"system/capability/request\", data: {grants: [], ttl_ms: null}} (requires put grant)"
    s = _handshake(ctx, Result("", "", ""))
    if s is None:
        return Arm("conformant", member, None, "could not look: handshake failed")
    res.witnesses["put_member_grant"] = grant_covers(s, "system/tree", "put")
    base = _put(s, _probe_path("r4b-base"), ident.entity("system/capability/request", {"grants": []}))
    with_null = _put(s, _probe_path("r4b-null"), ident.entity("system/capability/request", {"grants": [], "ttl_ms": None}))
    s.conn.close()
    res.witnesses["put_member"] = {"baseline": base.brief(), "with_member": with_null.brief()}
    if _posture_unmet(base) or _posture_unmet(with_null):
        return Arm("conformant", member, None, f"UNMEASURABLE under this posture: baseline {base.brief()}, member {with_null.brief()}")
    if base.kind != "response":
        return Arm("conformant", member, None, f"could not look: baseline put {base.brief()}")
    same = _outcome_class(with_null) == _outcome_class(base)
    return Arm("conformant", member, same, f"answered as the baseline put: {with_null.brief()}" if same
               else f"{with_null.brief()} where the baseline put got {base.brief()}")


def check_r4b(ctx: Ctx) -> Result:
    res = Result("ECP-R4-pending-b", "encoding/r4b_unknown_field_not_refused", "ENTITY-CORE-PROTOCOL §2.10, §1.3")
    base = _raw_hello(ctx, wire.hello_probe(Identity()))
    res.witnesses["baseline"] = base.brief()
    members = [("hello data: one extra key \"x_cnf_probe\": 1", (("x_cnf_probe", 1),)),
               ("hello data: extra key holding a nested map", (("x_cnf_probe", {"nested": {"deeper": [1, "two"]}}),))]
    arms = []
    for member, extra in members:
        o = _raw_hello(ctx, wire.hello_probe(Identity(), extra=extra))
        res.witnesses[member] = o.brief()
        if base.kind not in ("response", "close"):
            arms.append(Arm("conformant", member, None, f"could not look: baseline hello {base.brief()}"))
        else:
            same = _outcome_class(o) == _outcome_class(base)
            arms.append(Arm("conformant", member, same, f"answered as the baseline: {o.brief()}" if same else f"{o.brief()} where the baseline got {base.brief()}"))
    put_arm = _r4b_put_member(ctx, res)
    if put_arm.outcome.startswith("UNMEASURABLE under this posture"):
        # Not a could-not-look: the posture withholds this one member, and the hello members are no less measured for it.
        # Recorded as the file says ("UNMEASURABLE and reported so"), and the verdict covers the members that ran.
        res.witnesses["member_unmeasurable_under_posture"] = put_arm.outcome
    else:
        arms.append(put_arm)
    # WITNESS: the control as first written (F58) — the member in a tag. It borrows cbor-tag-rejected's verdict, so unscored.
    res.witnesses["tagged_member"] = _raw_hello(ctx, wire.hello_probe(Identity(), extra=(("x_cnf_probe", cbor.Tag(1, 1)),))).brief()
    # Control, suite-side: the comparator must tell three differing outcome pairs apart and hold one equal pair.
    ok200 = wire.Outcome("response", status=200)
    differing = [wire.Outcome("response", status=400, code="non_canonical_ecf"), wire.Outcome("close", detail="EOF"),
                 wire.Outcome("response", status=200, code="x")]
    detected = all(_outcome_class(ok200) != _outcome_class(d) for d in differing)
    equal = _outcome_class(ok200) == _outcome_class(wire.Outcome("response", status=200))
    control = Arm("negative-control", "control", detected and equal,
                  "comparator refused 3 differing pairs and held the equal one" if detected and equal else "comparator did NOT discriminate")
    _finish_arms(res, arms, control)
    return res


# ── encoding, put surface: ECP-R4, ECP-R41, …unsupported-content-hash-format-refused (+ ECP-R4-pending-b's put member) ──
#
# §6.3's `system/tree:put` is the one core surface that stores a caller's entity and serves it back, and the one where a
# mis-sized hash, a mismatched hash and an unsupported format code get DIFFERENT codes. Every file here needs
# `system/tree: put` on a path the suite owns. That is a POSTURE: the handshake grant decides it, not the peer's
# conformance. A 403 on a put is therefore never scored — the member is UNMEASURABLE under that posture, and the report
# carries the grant the handshake issued so a reader can see which posture it was.

PROBE_ROOT = "conformance-probe/prototype"


def _probe_path(tag: str) -> str:
    return f"{PROBE_ROOT}/{tag}-{os.urandom(6).hex()}"  # peer-relative; §5.4 canonicalize resolves it to the local peer


def _put(s: wire.Session, path: str, ent: object) -> wire.Outcome:
    s.conn.send(s.signed(wire.request_id("put"), "system/tree", "put", resource={"targets": [path]},
                         params=wire.tree_put_params(ent)))
    return s.read_response()


def _unbind(s: wire.Session, path: str) -> str:
    """Best-effort cleanup (§6.3 put with `entity` absent). Recorded, never scored."""
    s.conn.send(s.signed(wire.request_id("unbind"), "system/tree", "put", resource={"targets": [path]},
                         params=wire.tree_put_params(remove=True)))
    return s.read_response().brief().split(" (request_id")[0]


def _posture_unmet(o: wire.Outcome) -> bool:
    return o.kind == "response" and o.status == 403


def _put_posture_witness(s: wire.Session, res: Result) -> None:
    res.witnesses["precondition_put_grant"] = grant_covers(s, "system/tree", "put")


def returned_entity_bytes_equal(put: dict, got: wire.Outcome) -> tuple[bool | None, str]:
    """ECP-R4's assertion: `type`, `data` and `content_hash` of the entity `get` served, AS ENCODED BYTES, equal what was
    put. Decoded equality is exactly the lossy round-trip §5.4 rules out, so the bytes are sliced from the frame."""
    if got.kind != "response":
        return None, f"get: {got.brief()}"
    if got.status != 200:
        return False, f"accepted by put, then get answered {got.status} {got.code or '-'}"
    if got.raw is None or cbor.raw_at(got.raw, ("root", "data", "result")) is None:
        return False, "get 200 carries no result"
    diffs = []
    for f in ("type", "data", "content_hash"):
        served = cbor.raw_at(got.raw, ("root", "data", "result", f))
        sent = cbor.encode(put[f])
        if served != sent:
            diffs.append(f"{f}: sent {sent.hex()[:48]} served {served.hex()[:48] if served is not None else 'absent'}")
    return (True, "type, data and content_hash byte-identical") if not diffs else (False, "; ".join(diffs))


R4_MEMBERS = (
    ("an unknown top-level data field", "test/v1", {"x": 1, "x_cnf_unknown": "kept"}),
    ("an unknown field nested two maps deep", "test/v1", {"x": 1, "outer": {"inner": {"x_cnf_unknown": [1, "two"]}}}),
    ("a declared-optional-looking field whose value is null", "test/v1", {"x": 1, "x_cnf_optional": None}),
    ("a data field holding bytes shaped like a hash under unallocated format code 0x7E", "test/v1",
     {"ref": b"\x7e" + bytes(range(32))}),
    ("an unknown entity type string", "cnf-probe/unmodelled-type/v1", {"x": 1}),
    ("a float requiring half precision (1.5 → F9 3E00)", "test/v1", {"f": 1.5}),
    ("a map whose keys sort differently by insertion than canonically", "test/v1", {"zzz": 1, "b": 2, "aa": 3}),
)


def _raw_map(pairs: list[tuple[str, bytes]]) -> bytes:
    """A map written in the given order from already-encoded values — only for fixtures that must be non-canonical."""
    return bytes([0xA0 | len(pairs)]) + b"".join(cbor.encode(k) + v for k, v in pairs)


def _fixture_get(type_raw: bytes, data_raw: bytes, hash_raw: bytes) -> wire.Outcome:
    result = _raw_map([("data", data_raw), ("type", type_raw), ("content_hash", hash_raw)])
    rdata = _raw_map([("result", result), ("status", cbor.encode(200)), ("request_id", cbor.encode("fixture"))])
    body = _raw_map([("root", _raw_map([("data", rdata), ("type", cbor.encode(wire.RESPONSE))])), ("included", b"\xa0")])
    return wire.classify(body, len(body))


def r4_fixtures() -> tuple[list[tuple[str, dict, wire.Outcome]], tuple[dict, wire.Outcome]]:
    """Three self-consistent get responses each missing one member's content (must FAIL the assertion), and one faithful
    response (must hold). Every broken fixture's content_hash is correct FOR ITS OWN BYTES: an assertion that only checks
    the served entity's own hash passes all three, which is the defect the control exists to catch."""
    import hashlib
    enc = cbor.encode
    unknown = ident.entity("test/v1", {"x": 1, "x_cnf_unknown": "kept"})
    nulled = ident.entity("test/v1", {"x": 1, "x_cnf_optional": None})
    ordered = ident.entity("test/v1", {"zzz": 1, "b": 2, "aa": 3})
    stripped = ident.entity("test/v1", {"x": 1})
    insertion = _raw_map([("zzz", enc(1)), ("b", enc(2)), ("aa", enc(3))])
    insertion_hash = b"\x00" + hashlib.sha256(_raw_map([("data", insertion), ("type", enc("test/v1"))])).digest()
    broken = [
        ("unknown field stripped, rehashed", unknown, _fixture_get(enc("test/v1"), enc(stripped["data"]), enc(stripped["content_hash"]))),
        ("null dropped, rehashed", nulled, _fixture_get(enc("test/v1"), enc(stripped["data"]), enc(stripped["content_hash"]))),
        ("keys re-sorted by insertion, rehashed", ordered, _fixture_get(enc("test/v1"), insertion, enc(insertion_hash))),
    ]
    faithful = (unknown, _fixture_get(enc(unknown["type"]), enc(unknown["data"]), enc(unknown["content_hash"])))
    return broken, faithful


def check_r4(ctx: Ctx) -> Result:
    res = Result("ECP-R4", "encoding/r4_put_get_round_trip_byte_identical", "ENTITY-CBOR-ENCODING §5.4, ENTITY-CORE-PROTOCOL §1.8, §2.10")
    s = _handshake(ctx, res)
    if s is None:
        return res
    _put_posture_witness(s, res)
    arms, cleanup = [], {}
    for member, type_, data in R4_MEMBERS:
        path = _probe_path("r4")
        ent = ident.entity(type_, data)
        p = _put(s, path, ent)
        if p.kind != "response":
            arms.append(Arm("conformant", member, None, f"could not look: put {p.brief()}"))
            break
        if _posture_unmet(p):
            arms.append(Arm("conformant", member, None, f"UNMEASURABLE under this posture: put {p.status} {p.code or '-'}"))
            continue
        if p.status != 200:
            # A refusal here is ECP-R4-pending-b's question, not this file's: nothing was stored, so nothing can be preserved.
            arms.append(Arm("conformant", member, None, f"UNMEASURABLE: put refused {p.status} {p.code or '-'} — nothing stored to preserve"))
            continue
        s.conn.send(s.signed(wire.request_id("get"), "system/tree", "get", resource={"targets": [path]}))
        g = s.read_response()
        held, why = returned_entity_bytes_equal(ent, g)
        arms.append(Arm("conformant", member, held, why))
        cleanup[member] = _unbind(s, path)
    res.witnesses["unbind"] = cleanup
    s.conn.close()
    broken, faithful = r4_fixtures()
    refused = {name: returned_entity_bytes_equal(put, fx)[0] for name, put, fx in broken}
    kept = returned_entity_bytes_equal(*faithful)[0]
    ok = all(v is False for v in refused.values()) and kept is True
    control = Arm("negative-control", "control", ok,
                  f"assertion refused {sum(v is False for v in refused.values())} of 3 self-consistent lossy fixtures and "
                  f"{'held' if kept else 'did NOT hold'} the faithful one")
    _finish_arms(res, arms, control)
    return res


def _mis_sized_arm(name: str, o: wire.Outcome) -> Arm:
    if _posture_unmet(o):
        return Arm("conformant", name, None, f"UNMEASURABLE under this posture: {o.status} {o.code or '-'}")
    if o.kind != "response":
        return Arm("conformant", name, None, f"could not look: {o.brief()}")
    if o.status == 400 and o.code == "invalid_request":
        return Arm("conformant", name, True, "400 invalid_request")
    return Arm("conformant", name, False, f"{o.status} {o.code or '-'} — assertion (400 invalid_request) does not hold"
               + (" — the length check did not run before the comparison" if o.code == "hash_mismatch" else ""))


def check_r41(ctx: Ctx) -> Result:
    res = Result("ECP-R41", "encoding/r41_put_mis_sized_hash_invalid_request", "ENTITY-CORE-PROTOCOL §1.2, §6.3")
    s = _handshake(ctx, res)
    if s is None:
        return res
    _put_posture_witness(s, res)
    good = ident.entity("test/v1", {"x": 1})
    digest = good["content_hash"][1:]
    members = [("0x00 + 31-byte digest", b"\x00" + digest[:31]), ("0x00 + 33-byte digest", b"\x00" + digest + b"\x00")]
    advertised = s.responder_hello.get("hash_formats") if isinstance(s.responder_hello, dict) else None
    res.witnesses["responder_hash_formats"] = advertised if advertised is not None else "absent (§4.5: means [\"ecfv1-sha256\"])"
    if isinstance(advertised, list) and "ecfv1-sha384" in advertised:
        members.append(("0x01 + 32-byte digest (only if the peer advertises ecfv1-sha384)", b"\x01" + digest))
    else:
        res.witnesses["member_not_run"] = "0x01 + 32-byte digest: the peer does not advertise ecfv1-sha384 (the file's condition)"
    arms = []
    for name, h in members:
        o = _put(s, _probe_path("r41"), dict(good, content_hash=h))
        res.witnesses[name] = o.brief()
        arms.append(_mis_sized_arm(name, o))
        if o.kind != "response":
            break
    c = _put(s, _probe_path("r41-control"), dict(good, content_hash=wire.flip_last(good["content_hash"])))
    res.witnesses["control"] = c.brief()
    if _posture_unmet(c) or c.kind != "response":
        control = Arm("negative-control", "control", None, f"could not look: {c.brief()}")
    else:
        control = Arm("negative-control", "control", c.status == 400 and c.code == "hash_mismatch",
                      f"correctly sized, last digest byte flipped: {c.status} {c.code or '-'} (must be 400 hash_mismatch)")
    s.conn.close()
    _finish_arms(res, arms, control)
    return res


def check_unsupported_format(ctx: Ctx) -> Result:
    res = Result("UNALLOCATED-unsupported-content-hash-format-refused", "encoding/put_unsupported_content_hash_format",
                 "ENTITY-CORE-PROTOCOL §1.2, §4.7 row 5, §6.3")
    s = _handshake(ctx, res)
    if s is None:
        return res
    _put_posture_witness(s, res)
    good = ident.entity("test/v1", {"x": 1})
    o = _put(s, _probe_path("fmt7e"), dict(good, content_hash=b"\x7e" + good["content_hash"][1:]))
    res.witnesses["put_7e"] = o.brief()
    if _posture_unmet(o):
        conformant = Arm("conformant", "put-unsupported-format", None, f"UNMEASURABLE under this posture: {o.status} {o.code or '-'}")
    elif o.kind != "response":
        conformant = Arm("conformant", "put-unsupported-format", None, f"could not look: {o.brief()}")
    else:
        conformant = _coded_refusal("put-unsupported-format", o, 400, "unsupported_content_hash_format")
    path00 = _probe_path("fmt00")
    c = _put(s, path00, good)
    res.witnesses["put_00"] = c.brief()
    if c.kind == "response" and c.status == 200:
        res.witnesses["unbind"] = _unbind(s, path00)
    s.conn.close()
    if _posture_unmet(c) or c.kind != "response":
        control = Arm("negative-control", "control", None, f"could not look: {c.brief()}")
    else:
        control = Arm("negative-control", "control", c.status == 200, f"same entity, format byte 0x00: {c.status} {c.code or '-'} (must be 200)")
    # WITNESS-ONLY: row 5 is reachable on a hello, but the responder's precedence against §4.5a is unstated.
    res.witnesses["hello_7e"] = _raw_hello(ctx, wire.hello_probe(Identity(), root_format=0x7E)).brief()
    _finish(res, conformant, control)
    return res


# ── ECP-R66, ECP-R66-pending-c — §4.10(a) payload bound, and keeps serving ─────────────────────────

# §4.10(a) says "wire size" and does not say whether the §1.6 4-byte prefix counts. The probes straddle BOTH readings:
# over = bound + 1 PAYLOAD bytes (a frame of bound + 5), under = bound - 5 payload bytes (a frame of bound - 1). The
# file's "one byte" is kept under either reading, at the cost of four bytes of slack, and the witness says so.
PREFIX_AMBIGUITY = 4
MAX_PREFIX = 0xFFFFFFFF


def padded_execute(s: wire.Session, rid: str, payload_len: int) -> bytes | None:
    """A well-formed authenticated EXECUTE whose PAYLOAD (the CBOR envelope, not the prefix) is exactly payload_len
    bytes, padded through a primitive/any params entity. None if that length is not reachable (a CBOR header boundary)."""
    def build(n: int) -> bytes:
        return s.signed(rid, "conformance-probe/resource-bounds", "put", params=ident.entity("primitive/any", {"pad": b"\0" * n}))
    n = max(0, payload_len - (len(build(0)) - 4))
    for _ in range(4):
        fr = build(n)
        diff = payload_len - (len(fr) - 4)
        if diff == 0:
            return fr
        n = max(0, n + diff)
    return None


def _oversize_prefix_witness(ctx: Ctx, res: Result) -> None:
    """UNSCORED, and only when no bound is declared: the largest length a §1.6 prefix can state, with no body, on an
    established session. Whether that is over the peer's bound is unknowable without the declaration, so nothing is
    concluded from it — it records what the peer DOES, which is the evidence the declaration ask (X4) is argued from."""
    s = _handshake(ctx, Result("", "", ""))
    if s is None:
        res.witnesses["max_prefix_probe"] = "could not look: handshake failed"
        return
    s.conn.send(MAX_PREFIX.to_bytes(4, "big"))
    o = s.read_response(ctx.quiet_wait)
    after = s.read_response(1.0) if o.kind == "response" else None
    s.conn.close()
    res.witnesses["max_prefix_probe"] = f"prefix {MAX_PREFIX}, no body: {o.brief()}" + (f"; then {after.brief()}" if after else "")


def _classify_over(o: wire.Outcome, after: wire.Outcome | None) -> Arm:
    name = "refused"
    if o.kind == "response" and o.status == 413 and o.code == "payload_too_large":
        shape = "then close" if after is not None and after.kind == "close" else "correlated, connection open" if o.request_id else "uncorrelated"
        return Arm("conformant", name, True, f"413 payload_too_large ({shape})")
    if o.kind == "response":
        return Arm("conformant", name, False, f"{o.status} {o.code or '-'} — the over-bound envelope was answered on its merits, not refused for size")
    if o.kind == "close":
        return Arm("conformant", name, False, f"close without a coded frame ({o.detail}) — §4.10(a)'s MAY is close AFTER a best-effort coded frame")
    return Arm("conformant", name, None, f"{o.brief()} — an outcome the file's accepts and refuses do not classify")


def check_r66(ctx: Ctx) -> Result:
    res = Result("ECP-R66", "resource_bounds/r66_payload_over_declared_bound", "ENTITY-CORE-PROTOCOL §4.10(a)")
    bound = ctx.declared_max_payload
    res.witnesses["declared_max_payload"] = bound
    if bound is None:
        conformant = Arm("conformant", "refused", None, "precondition unmet: the run declares no max_payload — §4.10 makes the "
                         "value deployment-defined and the file forbids assuming 16 MiB; UNMEASURABLE under this posture")
        _oversize_prefix_witness(ctx, res)
        _finish(res, conformant, None)
        return res
    res.witnesses["prefix_ambiguity_bytes"] = PREFIX_AMBIGUITY
    s = _handshake(ctx, res)
    if s is None:
        return res
    over = padded_execute(s, wire.request_id("over"), bound + 1)
    if over is None:
        s.conn.close()
        res.message = f"could not look: no well-formed EXECUTE of exactly {bound + 1} payload bytes"
        return res
    s.conn.send(over)
    o = s.read_response()
    after = s.read_response(1.0) if o.kind == "response" else None
    s.conn.close()
    res.witnesses["over"] = f"payload {bound + 1}: {o.brief()}"
    conformant = _classify_over(o, after)

    control = None
    c = _handshake(ctx, Result("", "", ""))
    under = padded_execute(c, wire.request_id("under"), bound - 1 - PREFIX_AMBIGUITY) if c else None
    if c is None or under is None:
        control = Arm("negative-control", "control", None, "could not look: second handshake failed or no EXECUTE of the under size")
    else:
        c.conn.send(under)
        t = c.read_response()
        c.conn.close()
        res.witnesses["under"] = f"payload {bound - 1 - PREFIX_AMBIGUITY}: {t.brief()}"
        if t.kind == "response":
            control = Arm("negative-control", "control", t.status != 413, f"under-bound envelope: {t.status} {t.code or '-'}")
        else:
            control = Arm("negative-control", "control", None, f"could not look: under-bound envelope got {t.brief()}")
    _finish(res, conformant, control)
    return res


def _answered_on_fresh(ctx: Ctx) -> wire.Outcome:
    s = wire.handshake(ctx.addr, Identity(), ctx.timeout, ctx.sign_message)
    if isinstance(s, wire.HandshakeFailure):
        return s.outcome
    s.conn.send(s.signed(wire.request_id("fresh"), "system/tree", "get"))
    o = s.read_response()
    s.conn.close()
    return o


def check_r66c(ctx: Ctx) -> Result:
    res = Result("ECP-R66-pending-c", "resource_bounds/r66c_keeps_serving_after_over_bound", "ENTITY-CORE-PROTOCOL §4.10")
    bound = ctx.declared_max_payload
    res.witnesses["declared_max_payload"] = bound
    # The control runs FIRST: "answered at all under this posture" must be established before anything could kill the peer.
    base = _answered_on_fresh(ctx)
    res.witnesses["baseline"] = base.brief()
    control = Arm("negative-control", "control", base.kind == "response", f"fresh-connection request, nothing preceding: {base.brief()}")
    if control.held is False:
        control.held = None
        res.message = "could not look: the follow-up request is not answered even with no over-bound frame (the file's antecedent)"
    if bound is None:
        conformant = Arm("conformant", "still-serving", None, "precondition unmet: the run declares no max_payload, so no frame is "
                         "KNOWN to be over the bound; UNMEASURABLE under this posture")
        # WITNESS: after the largest prefix §1.6 can state, is a fresh connection answered? Unscored for the same reason.
        _oversize_prefix_witness(ctx, res)
        res.witnesses["fresh_after_max_prefix"] = _answered_on_fresh(ctx).brief()
        _finish(res, conformant, control)
        return res
    s = _handshake(ctx, res)
    if s is None:
        return res
    over = padded_execute(s, wire.request_id("over"), bound + 1)
    if over is not None:
        s.conn.send(over)
        res.witnesses["over"] = s.read_response().brief()
    s.conn.close()
    f = _answered_on_fresh(ctx)
    res.witnesses["after"] = f.brief()
    res.unreachable_is_observation = over is not None and control.held is True  # the peer answered before, and not after
    conformant = Arm("conformant", "still-serving", f.kind == "response" if over is not None else None,
                     f"fresh connection after the over-bound frame: {f.brief()}" if over is not None else "could not build the over-bound frame")
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
    "ECP-R47": check_r47,
    "ECP-R47-pending-b": check_r47b,
    "UNALLOCATED-hash-format-intersection": check_hash_format_intersection,
    "ECP-R2": check_r2,
    "ECP-R12": check_r12,
    "ECP-R7-pending-b": check_r7b,
    "UNALLOCATED-emitted-frames-are-canonical-ecf": check_frames_canonical,
    "UNALLOCATED-emitted-entities-conform-to-protocol-types": check_typed_fields,
    "UNALLOCATED-emitted-optional-fields-absent-not-null": check_optional_nulls,
    "ECP-R3": check_r3,
    "ECP-R7": check_r7,
    "UNALLOCATED-cbor-tag-rejected": check_cbor_tag,
    "UNALLOCATED-duplicate-map-key-rejected": check_dup_key,
    "ECP-R4-pending-b": check_r4b,
    "ECP-R4": check_r4,
    "ECP-R41": check_r41,
    "UNALLOCATED-unsupported-content-hash-format-refused": check_unsupported_format,
    # LAST, deliberately: these send the largest frames any check sends, and a peer that dies on one must not turn every
    # requirement after it into a could-not-look.
    "ECP-R66": check_r66,
    "ECP-R66-pending-c": check_r66c,
}

# The reference oracle's check each requirement file names — provenance only, for a consumer's category filter.
CATEGORY = {rid: "connectivity" for rid in CHECKS} | {"UNALLOCATED-key-type-mutual-verifiability": "negotiation",
                                                      "UNALLOCATED-hash-format-intersection": "negotiation",
                                                      "ECP-R66": "resource_bounds", "ECP-R66-pending-c": "resource_bounds"} \
    | {rid: "encoding" for rid in ("ECP-R2", "ECP-R12", "ECP-R7-pending-b", "UNALLOCATED-emitted-frames-are-canonical-ecf",
                                   "UNALLOCATED-emitted-entities-conform-to-protocol-types",
                                   "UNALLOCATED-emitted-optional-fields-absent-not-null", "ECP-R3", "ECP-R7",
                                   "UNALLOCATED-cbor-tag-rejected", "UNALLOCATED-duplicate-map-key-rejected", "ECP-R4-pending-b",
                                   "ECP-R4", "ECP-R41", "UNALLOCATED-unsupported-content-hash-format-refused")}


def run(rid: str, ctx: Ctx) -> Result:
    before = wire.UNREACHABLE[0]
    try:
        res = CHECKS[rid](ctx)
        missed = wire.UNREACHABLE[0] - before
        if missed:
            res.witnesses["connections_not_opened"] = missed
        if missed and not res.unreachable_is_observation and res.verdict != "SKIP":
            res.witnesses["verdict_withheld"] = f"{res.verdict}: {res.message}"
            for arm in res.arms:
                arm.held = None
            res.verdict = "SKIP"
            res.message = f"could not look: {missed} connection(s) to {ctx.addr} could not be opened, so no verdict is the peer's"
        return res
    except Exception as e:  # a suite defect is never a peer verdict
        return Result(rid, "suite-error", "", "SKIP",
                      f"SUITE DEFECT (not a peer result): {e.__class__.__name__}: {e}",
                      witnesses={"traceback": traceback.format_exc(limit=6)}, peer_attributable=False)
