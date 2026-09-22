#!/usr/bin/env python3
"""implements-gate — does the SUITE's code implement the snapshot its REQUIREMENT is authored at?

    tools/implements-gate.py              # every suites/*/IMPLEMENTS
    tools/implements-gate.py --self-test

⛔ **THE GAP THIS CLOSES, AND IT COST US A VOID MEASUREMENT (`F76`).** Every gate in this tree that
touches a suite measures a **declaration that the suite implements a requirement id**. None of them
can see **which VERSION of the obligation the code implements.** Twice, that was the difference
between a measurement and a wrong answer:

  * **`ECP-R57`** — its obligation INVERTED at `0.8.2.25` (`close` and `coded frame` swapped places,
    `F75`). The requirement file and its item were re-authored 2026-09-15; `check_r57` went on
    scoring `state == "close"`, the `.21` rule, until 2026-09-16.
  * **`ECP-R7`** — `0.8.2.24` PINNED its refusal code and the file was re-authored to say so.
    `check_r7` went on calling `_refused_any`, a helper whose own docstring says it is *"for rows
    that require REJECTION and PIN NO CODE."* ⭐ So the file's recorded **prediction** — that peers
    passing under the old reading would FAIL under the pin — **could not have fired**: the
    instrument passed every peer the prediction was about. **A prediction whose instrument cannot
    falsify it is not a prediction**, which is the charter's negative-control rule pointed at a
    prediction instead of an arm.

In both windows `make check` was green, `IMPLEMENTS` still named the id, and the
executed-by-a-suite ratchet still counted it. **Nothing was broken; everything was stale.**

⚠ **WHAT THIS GATE HONESTLY IS, SAID RATHER THAN IMPLIED.** The second column is a **declaration**
and a session can bump it without touching a line of check code. **No gate can verify that code
implements a re-authored obligation** — that is the same undecidability `AP-16` names for
*"does this summary agree with its source"* and `entity-system-generator` names for *"is this regex
the right regex."* The value is narrower and real: **bumping it is a conscious line in the diff**,
where the drift was previously invisible to every instrument including the reader.

⛔ **`unreviewed` IS THE HONEST DEFAULT AND IT IS COUNTED.** 26 of 28 rows carry it at first
measurement. Filling one in for a check nobody re-read would be the false claim this gate exists to
prevent, so the debt is a **down-only ratchet** (`IMPLEMENTS-REVIEW-DEBT`), lowered by reading a
check against its requirement — never by typing a version string.

⚠ **`D16` IS NOT VIOLATED, AND THE DISTINCTION IS THE WHOLE DESIGN.** `D16`/`F65` forbids a suite
asserting the snapshot it **validates against** — that must be DERIVED, because it is derivable and
hardcoding it goes stale silently. This column is the different fact of which snapshot the code was
**written** against. It cannot be derived from anything, and **its going stale is the signal**, not
the defect. `lint-suite-constants` scans `.py/.sh/.rs/.ts`; `IMPLEMENTS` is not suite source.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True   # __pycache__ is .gitignore'd; lint-ignored refuses it (AP-8)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402  — tools' OWN codec; never the suite's (lint-suite-independence)

ROOT = Path(__file__).resolve().parent.parent
SUITES = ROOT / "suites"
REQ_ROOT = ROOT / "requirements"
DEBT = SUITES / "IMPLEMENTS-REVIEW-DEBT"
UNREVIEWED = "unreviewed"

# The floor. This gate's fragile part is a glob and a two-field split, and both fail OPEN.
MIN_ROWS = 10


class GateError(Exception):
    """Could-not-look. Exits 2, never 1."""


def read_int(path: Path) -> int | None:
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                return int(line)
            except ValueError:
                return None
    return None


def rows(manifest: Path) -> list[tuple[str, str | None]]:
    out = []
    for line in manifest.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        out.append((parts[0], parts[1] if len(parts) > 1 else None))
    return out


def requirement_snapshot(rid: str) -> str | None:
    for spec_dir in sorted(p for p in REQ_ROOT.iterdir() if p.is_dir()):
        f = spec_dir / f"{rid}.diag"
        if f.is_file():
            try:
                return cbordiag.parse(f.read_text()).get("snapshot")
            except Exception as exc:                            # noqa: BLE001
                raise GateError(f"{f}: {exc}") from exc
    return None


def validate(manifest_rows: list[tuple[str, str | None]], suite: str,
             snap_of) -> tuple[list[str], int]:
    f, unreviewed = [], 0
    for rid, declared in manifest_rows:
        if declared is None:
            f.append(f"suites/{suite}/IMPLEMENTS: {rid!r} has no snapshot column. A row with one "
                     f"field cannot be distinguished from a row nobody has reviewed — write "
                     f"`{UNREVIEWED}` explicitly (F76).")
            continue
        if declared == UNREVIEWED:
            unreviewed += 1
            continue
        actual = snap_of(rid)
        if actual is None:
            f.append(f"suites/{suite}/IMPLEMENTS: {rid!r} names no requirement file")
        elif declared != actual:
            f.append(f"suites/{suite}/IMPLEMENTS: {rid!r} declares the check was authored against "
                     f"{declared!r}, but the requirement is authored at {actual!r}. ⛔ THE "
                     f"REQUIREMENT MOVED AND THE CODE DID NOT — re-read the check against the "
                     f"obligation, then update this column. Do NOT bump the column alone: that is "
                     f"the exact edit F75/F76 made invisible.")
    return f, unreviewed


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if not SUITES.is_dir():
        print("implements-gate: COULD NOT LOOK — no suites/", file=sys.stderr)
        return 2
    manifests = sorted(SUITES.glob("*/IMPLEMENTS"))
    if not manifests:
        print("implements-gate: COULD NOT LOOK — no suites/*/IMPLEMENTS", file=sys.stderr)
        return 2

    findings, total, unreviewed = [], 0, 0
    try:
        for m in manifests:
            r = rows(m)
            if len(r) < MIN_ROWS:
                print(f"implements-gate: COULD NOT LOOK — {m} has {len(r)} row(s), below "
                      f"MIN_ROWS={MIN_ROWS}. A manifest that has stopped parsing reports a clean "
                      f"run over nothing.", file=sys.stderr)
                return 2
            total += len(r)
            f, u = validate(r, m.parent.name, requirement_snapshot)
            findings += f
            unreviewed += u
    except GateError as exc:
        print(f"implements-gate: COULD NOT LOOK — {exc}", file=sys.stderr)
        return 2

    ceiling = read_int(DEBT)
    if ceiling is None:
        findings.append(f"{DEBT.relative_to(ROOT)} missing or unreadable — the review debt is a "
                        f"ratchet and a ratchet with no ceiling is not one")
    elif unreviewed > ceiling:
        findings.append(f"review debt ROSE: {unreviewed} check(s) declare `{UNREVIEWED}`, ceiling "
                        f"{ceiling}. It is lowered by READING a check against its requirement, "
                        f"never by typing a version string.")

    for x in findings:
        print(f"  FINDING {x}", file=sys.stderr)
    print(f"implements-gate: {total} implemented requirement(s) across {len(manifests)} suite(s) — "
          f"{len(findings)} finding(s)")
    print(f"  check authored against its requirement's snapshot: {total - unreviewed} of {total}"
          f"   |   `{UNREVIEWED}` {unreviewed} ≤ ceiling {ceiling}")
    if unreviewed:
        print(f"  ⚠ {unreviewed} check(s) have NEVER been read against the obligation they measure. "
              f"That is not a claim they are wrong — it is the honest statement that nothing here "
              f"has established which version of the rule they implement (F76, D15).")
    return 1 if findings else 0


def self_test() -> int:
    """Executed control: every rule planted, and the lookalikes the gate must stay SILENT on."""
    snaps = {"A": "s/v2", "B": "s/v2", "C": "s/v1"}
    planted = []

    f, u = validate([("A", "s/v2"), ("B", UNREVIEWED)], "t", snaps.get)
    planted.append(("a matching snapshot and an explicit `unreviewed` are accepted", not f and u == 1))

    # 1. ⛔ THE RULE. A requirement authored at v2 with a check declared at v1 is the F75/F76 state.
    f, _ = validate([("C", "s/v2")], "t", {"C": "s/v1"}.get)
    planted.append(("a check declared BEHIND its requirement is refused", len(f) == 1))

    # 2. ...and AHEAD is refused too. A check written for a snapshot the requirement is not at is
    #    the same defect mirrored, and a gate that only looks one way misses the re-authoring that
    #    lands the code first (AP-15: measure the defect, not one spelling of it).
    f, _ = validate([("C", "s/v2")], "t", {"C": "s/v1"}.get)
    g, _ = validate([("C", "s/v1")], "t", {"C": "s/v2"}.get)
    planted.append(("a check declared AHEAD of its requirement is refused too", len(g) == 1))

    # 3. A missing second column is NOT silently treated as unreviewed.
    f, u = validate([("A", None)], "t", snaps.get)
    planted.append(("a row with no snapshot column is refused, not defaulted", len(f) == 1 and u == 0))

    # 4. An id naming no requirement file.
    f, _ = validate([("Z", "s/v2")], "t", snaps.get)
    planted.append(("a row naming no requirement file is refused", len(f) == 1))

    # 5. SILENCE CONTROL: `unreviewed` must not be compared against anything and must not fire.
    f, u = validate([("C", UNREVIEWED)], "t", {"C": "s/v9"}.get)
    planted.append(("`unreviewed` is counted, never compared (no false finding)", not f and u == 1))

    failed = [n for n, ok in planted if not ok]
    for n in failed:
        print(f"SELF-TEST FAILED: {n}", file=sys.stderr)
    if failed:
        return 1
    print(f"implements-gate self-test: OK — {len(planted)} control(s) held; a check BEHIND and a "
          f"check AHEAD of its requirement are both refused, a missing column is not defaulted to "
          f"`{UNREVIEWED}`, and `{UNREVIEWED}` itself produces no finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
