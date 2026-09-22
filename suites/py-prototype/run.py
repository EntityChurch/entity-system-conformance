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

from prototype import checks, ed25519, ident  # noqa: E402

SUITE = "py-prototype"

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
            "requirement_set_digest": "unavailable (source tree, unbuilt)",
            "from": "source tree (unbuilt)"}


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
    if a.list_requirements:
        print(json.dumps({"suite": SUITE, "spec": spec_field(info, list(checks.CHECKS)),
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
        # trusted = the instrument itself is sound for this run: its self-check passed, no suite defect, and every
        # verdict it reached had a negative control that ran. It says nothing about whether the peer passed.
        "trusted": not broken and not suite_defects and counts["INCONCLUSIVE"] == 0,
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
