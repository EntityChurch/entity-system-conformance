#!/usr/bin/env python3
"""control-set-gate — the expected-outcome set is pinned to the obligation it was measured against.

    tools/control-set-gate.py              # check suites/CONTROL-SET.diag
    tools/control-set-gate.py --self-test  # the executed controls

WHY THIS EXISTS. Operator direction, 2026-09-16: a bring-up chunk must not be built against
requirements whose answers we do not already know, because **a suite reporting FAIL everywhere and a
suite that is simply broken produce identical output.** So a requirement is fit for bring-up only
when both of its outcome classes have been observed on real peers, and that observation has to live
somewhere a gate can read.

⛔ THE FAILURE MODE IT ACTUALLY GUARDS, AND IT HAPPENED WHILE THE FILE WAS BEING WRITTEN. The first
draft of the control set was built from the morning's run and recorded `ECP-R3: 3 PASS`. Those
verdicts had been scored against requirement text that no longer existed — ECP-R3's file digest was
`9714ce72…` in that run and `08155caf…` at HEAD, because the requirement was re-authored between the
two. A control set that records a verdict without the obligation's digest would have told a new
suite that three peers pass a rule none of them had ever been measured against. **That is AP-18 with
the blast radius pointed at the validator**, and it is why rule 1 below is the whole point of the
file.

WHAT IT CHECKS

  1. ⭐ Every row's `requirement_digest` matches the sha256 of the requirement file TODAY. A moved
     obligation reds the gate instead of silently invalidating the expectations under it.
  2. Every requirement a row names exists in `requirements/`.
  3. Every peer an expectation names is declared in the `peers` block, with a pin.
  4. `fit_for_bringup: true` requires BOTH a PASS and a FAIL expectation. A requirement every peer
     fails cannot distinguish a correct suite from a broken one — that is the founding criterion and
     it is mechanical, so it is checked rather than asserted.
  5. `fit_for_bringup: false` must say `why_unfit`. An unfit row with no reason reads as an oversight.
  6. Every expectation carries `class`, not just a verdict. A suite that collapses two distinct
     non-conformances into one FAIL gets the top-line verdict right on every peer, so ONLY the class
     catches it.
  7. Every declared peer carries `certified_by_contract`, explicitly. A pin says which bytes; a
     certification says they were checked, and the difference is never left to inference.

WHAT IT DELIBERATELY DOES NOT CHECK. Whether an expectation is CORRECT. It cannot: that is this
seat's judgement about a peer's behaviour, and challenging it is precisely what a second suite is
for. This gate keeps the file honest about its own provenance, nothing more.

Stdlib-only Python 3.11+. Exit 0 clean, 1 findings, 2 could-not-look — a gate that cannot see must
never read as a pass.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTROL_SET = ROOT / "suites" / "CONTROL-SET.diag"
REQ_ROOT = ROOT / "requirements"

VERDICTS = ("PASS", "FAIL", "SKIP", "WARN")


class Finding:
    __slots__ = ("rule", "where", "text")

    def __init__(self, rule: str, where: str, text: str):
        self.rule, self.where, self.text = rule, where, text

    def __str__(self) -> str:
        return f"  {self.rule:28} {self.where:22} {self.text}"


def _requirement_digest(rid: str) -> str | None:
    """sha256 of the requirement file's raw bytes — the same value build-info.py bakes into the
    bundle, so a row here and a verdict there are pinned to one text or neither is."""
    hits = sorted(REQ_ROOT.rglob(f"{rid}.diag"))
    if not hits:
        return None
    return hashlib.sha256(hits[0].read_bytes()).hexdigest()


def check(doc: dict) -> list[Finding]:
    findings: list[Finding] = []
    declared = {p.get("name"): p for p in doc.get("peers", []) if isinstance(p, dict)}

    for name, peer in declared.items():
        if not peer.get("pin"):
            findings.append(Finding("peer-no-pin", str(name),
                                    "declared with no `pin` — a peer named without its bytes is a label"))
        if "certified_by_contract" not in peer:
            findings.append(Finding("peer-certification-unstated", str(name),
                                    "no `certified_by_contract` — a pin says WHICH BYTES, a "
                                    "certification says they were CHECKED; never inferred"))

    rows = doc.get("rows", [])
    if not rows:
        findings.append(Finding("empty", "rows", "no rows — an empty control set is not a control set"))

    for row in rows:
        rid = row.get("requirement", "?")
        actual = _requirement_digest(rid)
        if actual is None:
            findings.append(Finding("requirement-missing", rid,
                                    "no such file under requirements/ — the row measures nothing"))
            continue

        pinned = str(row.get("requirement_digest", ""))
        if not pinned:
            findings.append(Finding("digest-absent", rid,
                                    "no `requirement_digest` — the expectations below it cannot be "
                                    "tied to any obligation text"))
        elif not actual.startswith(pinned):
            findings.append(Finding("digest-stale", rid,
                                    f"pinned {pinned} but the file is now {actual[:len(pinned)]} — "
                                    f"the obligation MOVED and every expectation under it was scored "
                                    f"against text that no longer exists"))

        exps = row.get("expectations", [])
        verdicts = set()
        for e in exps:
            peer = e.get("peer", "?")
            if peer not in declared:
                findings.append(Finding("peer-undeclared", f"{rid}/{peer}",
                                        "not in the `peers` block — a verdict with no pinned peer "
                                        "behind it is not a control"))
            v = e.get("expect")
            if v not in VERDICTS:
                findings.append(Finding("verdict-unknown", f"{rid}/{peer}",
                                        f"`expect` is {v!r}, not one of {'/'.join(VERDICTS)}"))
            else:
                verdicts.add(v)
            if not e.get("class"):
                findings.append(Finding("class-absent", f"{rid}/{peer}",
                                        "no `class` — two distinct non-conformances collapse to one "
                                        "FAIL and the top-line verdict hides it"))
            if not e.get("observed"):
                findings.append(Finding("observation-absent", f"{rid}/{peer}",
                                        "no `observed` — an expectation with no wire behaviour "
                                        "behind it is an opinion"))

        fit = row.get("fit_for_bringup")
        if fit is True:
            if not ({"PASS", "FAIL"} <= verdicts):
                findings.append(Finding("bringup-one-armed", rid,
                                        f"declared fit but the expectations are {sorted(verdicts) or 'empty'} "
                                        f"— without BOTH a PASS and a FAIL, a correct suite and a "
                                        f"broken one produce identical output"))
            if not row.get("why_fit"):
                findings.append(Finding("fit-unjustified", rid, "declared fit with no `why_fit`"))
        elif fit is False:
            if not row.get("why_unfit"):
                findings.append(Finding("unfit-unexplained", rid,
                                        "declared unfit with no `why_unfit` — unfit and forgotten "
                                        "read the same from outside"))
        else:
            findings.append(Finding("fitness-undeclared", rid,
                                    "no `fit_for_bringup` — the one question the file exists to answer"))

    return findings


def _report(doc: dict) -> None:
    rows = doc.get("rows", [])
    fit = [r for r in rows if r.get("fit_for_bringup") is True]
    peers = doc.get("peers", [])
    durable = {e.get("peer") for r in rows for e in r.get("expectations", []) if e.get("durable") is True}
    volatile = {e.get("peer") for r in rows for e in r.get("expectations", []) if e.get("durable") is False}
    print(f"control-set-gate: {len(rows)} row(s) over {len(peers)} peer(s) — "
          f"{len(fit)} fit for bring-up")
    if fit:
        print(f"  fit: {', '.join(r['requirement'] for r in fit)}")
    if volatile:
        print(f"  ⚠ {len(volatile)} peer(s) pinned to UNCOMMITTED bytes and not durable: "
              f"{', '.join(sorted(str(v) for v in volatile))}")
    if durable:
        print(f"  durable peers: {', '.join(sorted(str(d) for d in durable))}")
    print("  ⛔ A COMPARISON SET, NEVER AN ANSWER KEY. A new suite disagreeing with a row is one of "
          "three things and finding out which is the job.")


# --------------------------------------------------------------------------- self-test

_CLEAN = {
    "peers": [
        {"name": "alpha", "pin": "image_id deadbeef", "certified_by_contract": False},
        {"name": "beta", "pin": "head cafe1234, clean", "certified_by_contract": False},
    ],
    "rows": [
        {"requirement": "__SELFTEST__", "requirement_digest": "__DIGEST__",
         "fit_for_bringup": True, "why_fit": "both arms observed",
         "expectations": [
             {"peer": "alpha", "expect": "PASS", "class": "coded_response",
              "observed": "400 hash_mismatch", "durable": True},
             {"peer": "beta", "expect": "FAIL", "class": "bare_close",
              "observed": "EOF after 0 of 4 bytes", "durable": False},
         ]},
    ],
}


def _mutate(base: dict, fn) -> dict:
    import copy
    d = copy.deepcopy(base)
    fn(d)
    return d


def self_test() -> int:
    import copy
    import tempfile

    global REQ_ROOT
    holds, breaks = 0, 0

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        req = tmp / "selftest"
        req.mkdir()
        body = '{\n  "id": "__SELFTEST__"\n}\n'
        (req / "__SELFTEST__.diag").write_text(body)
        real_digest = hashlib.sha256(body.encode()).hexdigest()
        REQ_ROOT = tmp

        def prime(d):
            s = copy.deepcopy(d)
            for r in s["rows"]:
                if r.get("requirement_digest") == "__DIGEST__":
                    r["requirement_digest"] = real_digest[:16]
            return s

        clean = prime(_CLEAN)
        f = check(clean)
        if f:
            print("SELF-TEST FAIL: the clean control set produced findings:")
            for x in f:
                print(x)
            return 1
        holds += 1

        # --- planted defects: each MUST produce at least one finding ----------------
        planted = [
            ("digest moved under the row",
             lambda d: d["rows"][0].update(requirement_digest="0000000000000000")),
            ("no digest at all",
             lambda d: d["rows"][0].pop("requirement_digest")),
            ("requirement file does not exist",
             lambda d: d["rows"][0].update(requirement="__NOPE__")),
            ("fit, but every peer fails",
             lambda d: d["rows"][0]["expectations"][0].update(expect="FAIL")),
            ("fit, but every peer passes",
             lambda d: d["rows"][0]["expectations"][1].update(expect="PASS")),
            ("fit with no justification",
             lambda d: d["rows"][0].pop("why_fit")),
            ("unfit with no reason",
             lambda d: d["rows"][0].update(fit_for_bringup=False, why_unfit=None)),
            ("fitness not declared at all",
             lambda d: d["rows"][0].pop("fit_for_bringup")),
            ("expectation names an undeclared peer",
             lambda d: d["rows"][0]["expectations"][0].update(peer="ghost")),
            ("expectation carries no outcome class",
             lambda d: d["rows"][0]["expectations"][0].pop("class")),
            ("expectation carries no observation",
             lambda d: d["rows"][0]["expectations"][1].pop("observed")),
            ("verdict outside the vocabulary",
             lambda d: d["rows"][0]["expectations"][0].update(expect="probably fine")),
            ("peer declared with no pin",
             lambda d: d["peers"][0].pop("pin")),
            ("peer certification left to inference",
             lambda d: d["peers"][1].pop("certified_by_contract")),
            ("no rows",
             lambda d: d.update(rows=[])),
        ]
        for name, fn in planted:
            got = check(_mutate(clean, fn))
            if got:
                breaks += 1
            else:
                print(f"SELF-TEST FAIL: planted defect produced NO finding — {name}")
                return 1

        # --- negative controls: shapes the gate MUST stay silent on (AP-15) --------
        silent = [
            ("an unfit row that says why",
             lambda d: d["rows"][0].update(fit_for_bringup=False,
                                           why_unfit="witness-only, produces no verdict")),
            ("two PASS peers answering DIFFERENT codes — legal where the code is unasserted",
             lambda d: d["rows"][0]["expectations"].append(
                 {"peer": "beta", "expect": "PASS", "class": "coded_response",
                  "observed": "400 non_canonical_ecf", "durable": True})),
            ("a peer pinned to uncommitted bytes — reported, never a finding",
             lambda d: d["rows"][0]["expectations"][0].update(durable=False)),
            ("a SKIP expectation on an unfit row",
             lambda d: (d["rows"][0].update(fit_for_bringup=False, why_unfit="witness-only"),
                        d["rows"][0]["expectations"][0].update(expect="SKIP"))),
        ]
        for name, fn in silent:
            got = check(_mutate(clean, fn))
            if got:
                print(f"SELF-TEST FAIL: gate fired on a shape it must stay silent on — {name}")
                for x in got:
                    print(x)
                return 1
            holds += 1

    print(f"control-set-gate self-test: OK — clean set accepted, {breaks} planted defect(s) refused, "
          f"{holds} negative control(s) held (including two PASS peers answering different codes, "
          f"which is legal wherever the requirement leaves the code unasserted)")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if not CONTROL_SET.is_file():
        print(f"control-set-gate: could not look — {CONTROL_SET} is absent", file=sys.stderr)
        return 2
    try:
        doc = cbordiag.parse(CONTROL_SET.read_text())
    except Exception as exc:  # noqa: BLE001 — a parse failure is could-not-look, never a pass
        print(f"control-set-gate: could not look — {CONTROL_SET} does not parse: {exc}", file=sys.stderr)
        return 2

    findings = check(doc)
    for f in findings:
        print(f)
    _report(doc)
    if findings:
        print(f"  {len(findings)} finding(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
