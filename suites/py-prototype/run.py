"""py-prototype — suite 1. Entry point for every instrument slot.

Argv is `validate-peer`-shaped because the slots that exec it (Keystone's census `--probe`, the generator's
`host-launch`) pass that shape: `-addr H:P [-reference-peer H:P] -profile core -json-out PATH`. Single- and
double-dash spellings are both accepted. Flags this suite does not act on are RECORDED in the report, never
silently dropped — an ignored input that changes nothing is still an input someone assumed mattered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prototype import cbor, checks, ed25519, ident  # noqa: E402

SUITE = "py-prototype"

# The canonical CBOR of the requirements this bundle implements, written by `make build`
# (tools/build-info.py --requirements-out). Its sha256 is BUILD.json's `implemented_set_digest`.
# ⛔ NOT a spec-data path and not a snapshot: it is a build output of THIS repo's requirement corpus.
REQUIREMENT_ARTIFACT = "requirements.cbor"

# ⛔ There is deliberately NO snapshot constant here naming a spec-data/ directory, and there must never be one again.
# `snapshot` is a field on every requirement file (spec-data/README.md rule 3). A constant here restates an
# input the requirement set already carries, cannot disagree with it loudly, and stamps the guess into
# `spec.*` — which is the COMPARABILITY ANCHOR of the verdict document. It was correct for exactly as long as
# every requirement cited one snapshot, and wrong from the first re-base onward. See F65 / AP-13 / D16; the
# same shape as F43's hand-typed posture. A run has a snapshot SET and it is DERIVED, never asserted.
# `make lint-suite-independence` refuses any suite constant naming a spec-data/ directory.


def _snapshot_of(path: Path) -> str:
    """The requirement's own `snapshot` field, read as TEXT.

    Deliberately not a parse: this path runs only from an unbuilt source tree, and pulling a CBOR
    diagnostic-notation parser in here to read one field would put a second codec in the suite for
    no measurement. The built bundle gets the value from BUILD.json, where `make build` put it
    using tools' own codec."""
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith('"snapshot"'):
            return s.split(":", 1)[1].strip().rstrip(",").strip().strip('"')
    return "undeclared"


def build_info() -> dict:
    """Written by `make build` into the bundle: suite version, and the sha256 AND DECLARED SNAPSHOT of every
    requirement file this suite implements, so each verdict names the exact requirement text it measured and
    the exact spec text that text was authored against. Run from the source tree instead, both are computed
    from ../../requirements/entity-core-protocol, and the report says so."""
    p = HERE / "BUILD.json"
    if p.is_file():
        info = json.loads(p.read_text())
        info["from"] = "bundle"
        info.setdefault("requirement_snapshots", {})
        return info
    reqs = HERE.parent.parent / "requirements" / "entity-core-protocol"
    digests, snaps = {}, {}
    for rid in checks.CHECKS:
        f = reqs / f"{rid}.diag"
        digests[rid] = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else "unavailable"
        snaps[rid] = _snapshot_of(f) if f.is_file() else "unavailable"
    return {"suite_version": "source-tree", "requirement_digests": digests, "requirement_snapshots": snaps,
            "implemented_set_digest": "unavailable (source tree, unbuilt)",
            "from": "source tree (unbuilt)"}


def requirement_set(info: dict) -> tuple[dict | None, str]:
    """The implemented requirement set, decoded from the bundle with THIS SUITE'S OWN codec.

    ⭐ This is where the two independent canonical-CBOR implementations meet on the RUN path.
    `tools/cbordiag.py` wrote these bytes; `prototype/cbor.py` decodes and re-encodes them and must
    reproduce them exactly. `make lint-suite-independence` forbids the two sharing a line, and the
    entire argument for paying for the second is that a disagreement between them is INFORMATION —
    so something has to be able to surface one. Until 2026-09-15 only `make test` could, and only
    when `make corpus` had been run first.

    Returns `(by_id, note)`. `by_id` is None — and the run reports itself untrusted — whenever the
    anchor could not be established. ⛔ A missing anchor is never silently treated as a passing one:
    that is the substitution `GUIDE-CONFORMANCE` §3.1 item 7 exists to ban."""
    p = HERE / REQUIREMENT_ARTIFACT
    if not p.is_file():
        return None, (f"absent — no {REQUIREMENT_ARTIFACT} beside the instrument (unbuilt source tree). "
                      f"THE PER-RUN ANCHOR AND THE TWO-CODEC CROSS-CHECK DID NOT RUN.")
    raw = p.read_bytes()
    try:
        obj, findings = cbor.decode(raw)
    except Exception as e:                                    # noqa: BLE001 — any decode failure is the same verdict
        return None, f"REFUSED — this suite's decoder cannot read the requirement artifact: {e}"
    if findings.tags or findings.non_canonical:
        return None, (f"REFUSED — the requirement artifact is not canonical to this suite's decoder: "
                      f"tags={findings.tags} non_canonical={findings.non_canonical}")
    if cbor.encode(obj) != raw:
        return None, ("REFUSED — THE TWO CODECS DISAGREE ABOUT CANONICAL FORM. tools/cbordiag.py wrote "
                      "these bytes; this suite decoded and re-encoded them and got different ones. Every "
                      "anchor in this report would be a number the two halves of this repo do not agree on.")
    seen = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    declared = info.get("implemented_set_digest")
    if declared and not declared.startswith("unavailable") and seen != declared:
        return None, (f"REFUSED — the artifact's sha256 ({seen}) is not the implemented_set_digest "
                      f"BUILD.json declares ({declared}). The bundle's two halves came from different builds.")
    # Artifact keys are `<spec>/<id>`; the suite knows ids. Derive the mapping rather than
    # constant-ing a directory name into the instrument (D16 / AP-13).
    return {str(k).rsplit("/", 1)[-1]: (str(k), v) for k, v in obj.items()}, "ok"


def anchor_field(info: dict, by_id: dict | None, note: str, selected: list[str]) -> dict:
    """⭐ `GUIDE-CONFORMANCE` §3.1 item 7 — *a verdict is the check-set actually asserted, never a
    proxy for it.* A published number MUST be anchored on a digest over the EXACT assertions in the
    run, count AND content.

    So this is computed over `selected`, not over what the bundle implements. Reporting the
    implemented-set digest on a `-category` run would anchor the number on a set LARGER than the one
    asserted — the "tracks which checks ran rather than what they assert" family the clause bans,
    arriving from the other direction. Routed to us by `entity-system-generator`, 2026-09-15."""
    # Named rather than left to inference, and named DIFFERENTLY: this is the BUILD fact — what the
    # bundle implements — and it is provenance, never the anchor. Giving it the anchor's name is the
    # substitution §3.1 item 7 bans, and is the same defect `entity-system-generator` is fixing on
    # their own `corpus digest:` print line (a membership value under a content value's name).
    build = {"implemented_set_digest": info.get("implemented_set_digest"),
             "implemented_set_size": info.get("implemented_set_size", len(checks.CHECKS))}
    if by_id is None:
        return {"requirement_set_digest": "unavailable", "requirement_set_size": len(selected),
                "scope": "the requirements this run asserted", "established": False, "why": note, **build}
    missing = [r for r in selected if r not in by_id]
    sel = {by_id[r][0]: by_id[r][1] for r in selected if r in by_id}
    return {
        "requirement_set_digest": f"sha256:{hashlib.sha256(cbor.encode(sel)).hexdigest()}",
        "requirement_set_size": len(sel),
        "scope": "the requirements this run asserted",
        "established": not missing,
        "codec": "the instrument's own canonical-CBOR encoder, over requirements it decoded itself",
        "two_codec_crosscheck": "PASSED — tools' canonical bytes reproduce under this suite's codec",
        **build,
        **({"established": False, "missing_from_artifact": missing,
            "why": "requirements were selected that the bundle's artifact does not carry, so the "
                   "anchor cannot describe what was asserted"} if missing else {}),
    }


def spec_field(info: dict, selected: list[str]) -> dict:
    """The verdict's `spec` block, DERIVED from the requirements actually selected for THIS run.

    A set, never a scalar: a run legitimately spans snapshots — mid-re-base within one area, and always once
    a peer is measured against core plus an extension. `mixed` is not a defect to hide; it is the fact a
    consumer needs in order to know what two reports may be compared on."""
    snaps = {info.get("requirement_snapshots", {}).get(r, "unavailable") for r in selected}
    return {"snapshots": sorted(snaps),
            "by_requirement": {r: info.get("requirement_snapshots", {}).get(r, "unavailable") for r in selected},
            "homogeneous": len(snaps) == 1}


def self_check() -> str | None:
    """A broken runtime must not produce peer verdicts. Two spec-anchored values, checked every run."""
    if ident.content_hash("system/empty", {}).hex() != "005f3139e342f5ef35c1e0eb3140c4511c469d604979d20542bc2ab92fd0ca396b":
        return "content_hash of {type: system/empty, data: {}} does not match ENTITY-CBOR-ENCODING Appendix A.1"
    seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
    if ed25519.sign(seed, b"").hex()[:16] != "e5564300c360ac72":
        return "Ed25519 does not reproduce RFC 8032 §7.1 TEST 1"
    return None


def parse(argv: list[str]):
    ap = argparse.ArgumentParser(prog=SUITE, allow_abbrev=False, add_help=True)
    ap.add_argument("-addr", "--addr", default=os.environ.get("ADDR"))
    ap.add_argument("-peer", "--peer", default=None, help="a label for the peer under test")
    ap.add_argument("-profile", "--profile", default="core")
    ap.add_argument("-category", "--category", default=None)
    ap.add_argument("-requirements", "--requirements", default=None, help="comma-separated requirement ids")
    ap.add_argument("-json-out", "--json-out", default=None)
    ap.add_argument("-timeout", "--timeout", default=None, help="accepted for slot compatibility; per-read timeout is -read-timeout")
    ap.add_argument("-read-timeout", "--read-timeout", type=float, default=10.0)
    ap.add_argument("-quiet-wait", "--quiet-wait", type=float, default=5.0)
    ap.add_argument("-reference-peer", "--reference-peer", default=None)
    ap.add_argument("-sign-message", "--sign-message", choices=ident.SIGN_MESSAGES, default="hash33")
    ap.add_argument("-posture-grants", "--posture-grants", default=None)
    ap.add_argument("-posture-pre-dispatch-layer", "--posture-pre-dispatch-layer", action="store_true")
    ap.add_argument("-declared-max-payload", "--declared-max-payload", type=int, default=None,
                    help="the peer's CONFIGURED §4.10(a) bound in bytes, from its posture. Absent = undeclared: ECP-R66 SKIPs")
    ap.add_argument("-list-requirements", "--list-requirements", action="store_true")
    return ap.parse_known_args(argv)


def main(argv: list[str]) -> int:
    a, unknown = parse(argv)
    info = build_info()
    by_id, anchor_note = requirement_set(info)
    if a.list_requirements:
        # What this instrument DECLARES without running — and the value is a content digest over the
        # declared requirements, not a membership hash of their names. `entity-system-generator`
        # flagged that exact collision (their open G-4 to entity-core-go): §3.1 item 7 reserves the
        # "set digest" name for a digest over ASSERTIONS, and shipping a membership value under it
        # hands the ecosystem the proxy by name.
        print(json.dumps({"suite": SUITE, "spec": spec_field(info, list(checks.CHECKS)),
                          "declared": anchor_field(info, by_id, anchor_note, list(checks.CHECKS)),
                          "requirements": info["requirement_digests"]}, indent=2))
        return 0
    if not a.addr:
        print(f"{SUITE}: -addr is required", file=sys.stderr)
        return 2
    if a.json_out and "status/CONFORMANCE-REPORT" in a.json_out:
        # Keystone's publication boundary: a probe is not a conformance report and must not overwrite one.
        print(f"{SUITE}: REFUSING to write {a.json_out} — a status/CONFORMANCE-REPORT is not ours to write", file=sys.stderr)
        return 2

    selected = list(checks.CHECKS)
    if a.requirements:
        want = [r.strip() for r in a.requirements.split(",") if r.strip()]
        selected = [r for r in want if r in checks.CHECKS]
    if a.category:
        selected = [r for r in selected if checks.CATEGORY.get(r) == a.category]

    anchor = anchor_field(info, by_id, anchor_note, selected)
    broken = self_check()
    ctx = checks.Ctx(a.addr, a.read_timeout, a.sign_message, a.posture_pre_dispatch_layer, a.quiet_wait,
                     a.declared_max_payload)
    started = time.time()
    results = [] if broken else [checks.run(r, ctx) for r in selected]

    counts = {v: sum(1 for r in results if r.verdict == v) for v in ("PASS", "WARN", "FAIL", "INCONCLUSIVE", "SKIP")}
    if broken:
        status, code = "ERROR", "self-check"
    elif counts["FAIL"]:
        status, code = "FAIL", next(r.requirement_id for r in results if r.verdict == "FAIL")
    elif counts["INCONCLUSIVE"]:
        status, code = "INCONCLUSIVE", next(r.requirement_id for r in results if r.verdict == "INCONCLUSIVE")
    elif counts["SKIP"]:
        status, code = "SKIP", next(r.requirement_id for r in results if r.verdict == "SKIP")
    else:
        status, code = "PASS", ""
    suite_defects = [r.requirement_id for r in results if r.suite_check == "suite-error"]

    report = {
        "suite": {"name": SUITE, "version": info.get("suite_version"), "runtime": sys.version.split()[0], "build": info.get("from")},
        "spec": spec_field(info, selected),
        # ⭐ GUIDE-CONFORMANCE §3.1 item 7's half of the dual anchor, over what THIS RUN asserted.
        # The other half is `suite.version`. A match on only one is not a match.
        "anchor": anchor,
        "profile": a.profile,
        "requirement_digests": {r: info["requirement_digests"].get(r) for r in selected},
        "posture": {
            "declared_by_invocation": a.posture_grants is not None,
            "grants": a.posture_grants or "not passed to the instrument — collected from the launching harness (tools/collect-run.py)",
            "pre_dispatch_layer": a.posture_pre_dispatch_layer,
            "declared_limits": {"max_payload": a.declared_max_payload},
            "transport": "tcp",
        },
        "sign_message": a.sign_message,
        "peers": [{"label": "subject", "addr": a.addr, "name": a.peer}],
        "ignored_inputs": {k: v for k, v in {"reference_peer": a.reference_peer, "timeout": a.timeout,
                                              "unrecognized": unknown or None}.items() if v},
        "started_at": int(started), "duration_s": round(time.time() - started, 3),
        # Keystone's census reads these two groups (F41): summary counts, and a one-line probe row.
        "summary": {"total": len(results), "passed": counts["PASS"], "warned": counts["WARN"], "failed": counts["FAIL"],
                    "skipped": counts["SKIP"] + counts["INCONCLUSIVE"], "inconclusive": counts["INCONCLUSIVE"],
                    "peer_attributable": sum(1 for r in results if r.peer_attributable),
                    # checks whose verdict was withheld because a connection to the peer could not be opened (F57)
                    "unreachable": sum(1 for r in results if "connections_not_opened" in r.witnesses)},
        "peer": a.peer or a.addr, "status": status, "code": code,
        # trusted = the instrument itself is sound for this run: its self-check passed, no suite defect, every
        # verdict it reached had a negative control that ran, AND the run can say what it asserted. It says
        # nothing about whether the peer passed.
        # ⛔ The anchor clause added 2026-09-15: a verdict whose check-set digest could not be established is
        # a number nobody can compare to another number, which under GUIDE-CONFORMANCE §3.1 item 7 is not a
        # publishable measurement. It must not read as trusted merely because the peer answered.
        "trusted": (not broken and not suite_defects and counts["INCONCLUSIVE"] == 0
                    and anchor.get("established") is True),
        "self_check": broken or "ok",
        "results": [r.__dict__ | {"arms": [arm.__dict__ for arm in r.arms]} for r in results],
    }
    text = json.dumps(report, indent=2, default=lambda o: o.hex() if isinstance(o, (bytes, bytearray)) else repr(o))
    if a.json_out:
        Path(a.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json_out).write_text(text + "\n")
    for r in results:
        print(f"{r.verdict:<12} {r.requirement_id:<8} {r.message}")
        for arm in r.arms:
            print(f"    {arm.kind:<16} {arm.name:<44} {'held' if arm.held else 'NOT HELD' if arm.held is False else 'n/a'}: {arm.outcome}")
    print(f"{SUITE}: {status} — {counts} against {a.addr} (signing {a.sign_message}){' SELF-CHECK FAILED: ' + broken if broken else ''}")
    return 2 if broken else 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
