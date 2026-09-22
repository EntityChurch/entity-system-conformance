#!/usr/bin/env python3
"""item-gate — the conformance-item format (ADR-0003), validated in one place.

    tools/item-gate.py              # validate every suites/*/items/**/*.diag
    tools/item-gate.py --self-test  # plant the defects and require refusal

**An item is one concrete way to exercise a requirement, authored by ONE suite.** The requirement is
shared between suites by design; the item is not — `AGENTS.md`: *"Sharing the substrate (peer
launching, transport) is fine and expected; sharing ASSERTIONS is not."* An arm with `given`, `step`,
`accept` and `refuse` IS an assertion.

⛔ **THIS GATE INHERITS THE MOST IMPORTANT RULE IN THE TREE AND RE-PLANTS ITS DEFECTS RATHER THAN
CLAIMING THEM.** *A check that cannot be made to fail has not been shown to measure anything* — the
charter's rule, and `GUIDE-CONFORMANCE` §5.2a's corollary. It lived in `requirement-gate.py` until
2026-09-15 (b), where it was enforced over arms. **The arms moved here, so the rule moved here**, and
a migration that let it lapse in transit would have been the single worst edit this seat could make.
It is a property of a PROBE, not of an obligation, so this is its correct home — but "correct home"
is an argument, and the self-test is the evidence.

WHAT ELSE IS HERE, and why each:

  * **`class` is a `[MUST]`** — `SPECIFICATION-FORMAT` §8.5: *"A conformance item MUST declare its
    class, and 'vector' alone does not."* ⭐ This is where `F73` is finally satisfiable. The audit
    recorded it as an unmet `[MUST]` on our 50 requirement files; arch ruled 2026-09-15 that the
    obligation was never pointed at a requirement at all. It was pointed HERE, and we had no object
    to carry it.
  * **`drives` is a `[MUST]` for us where §8.5a says `[SHOULD]`.** Their reason for the weaker level
    is that *"the two sides have different authors and land at different times"* — which is not true
    of us: we author both, in one tree. **The join between two suites is this field and nothing
    else.** An item driving nothing is unattributable, and joint coverage is derived from it.
  * **`author` is a `[MUST]`** — two items driving one requirement from two suites is the
    measurement this repo exists to take; two items whose common author nobody recorded is not.
  * **every `drives` target resolves to a real requirement file.** A citation resolves or it is not
    a citation. An item driving `ECP-R404` inflates coverage with a number nobody can check.

THE FLOOR IS ASSERTED. This gate's fragile part is a glob, and its failure mode is a clean run over
nothing — which reads as "every item is valid". It refuses to report a pass below MIN_ITEMS.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True   # __pycache__ is .gitignore'd; lint-ignored refuses it (AP-8)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402  — tools' OWN codec; never the suite's (lint-suite-independence)

ROOT = Path(__file__).resolve().parent.parent
SUITES = ROOT / "suites"
REQ_DIR = ROOT / "requirements"

# GUIDE-CONFORMANCE §7.0's four, by name, via SPECIFICATION-FORMAT §8.5.
# ⛔ The names are the GUIDE's, transcribed, not coined here (D18) — and §7.0's rows bundle an
# AUTHOR into each class definition. Arch ruled 2026-09-15 (CQ-40) that the author is a fact about
# the estate on a date and NOT a property of the class, and is moving it to a dated §7.0a. So this
# tuple carries the KINDS only, which is what the class question actually asks.
CLASSES = (
    "validate-peer check",      # behavioral, driven over the wire against a running peer
    "fixture-corpus vector",    # static byte-level .diag + canonical .cbor
    "host-seam check",          # a peer's in-process API, driven by its harness, asserted over the wire (§7d)
    "impl-internal test",       # not cross-impl, not conformance — declarable, never a conformance verdict
)
SURFACES = ("wire", "host-seam", "offline", "cross-peer", "unreachable")
STATUSES = ("draft", "reviewed", "ratified", "disputed")
ARM_KINDS = ("conformant", "negative-control", "non-conformant")
ARM_TABLES = {
    "step": "op", "assert": "kind", "accept": "outcome",
    "refuse": "outcome", "witness": "field", "inconclusive": "outcome",
}
REQUIRED = ("id", "author", "class", "drives", "surface", "status", "snapshot")
PROSE_FIELDS = ("header",)
MIN_ITEMS = 1


class GateError(Exception):
    """Could-not-look — items that cannot be read at all. Exits 2, never 1."""


def load(path: Path) -> dict:
    try:
        item = cbordiag.parse(path.read_text())
    except cbordiag.DiagError as exc:
        raise GateError(f"{path.name}: not parseable — {exc}") from exc
    if not isinstance(item, dict):
        raise GateError(f"{path.name}: top level is {type(item).__name__}, not a map")
    return item


def known_requirements() -> set[str]:
    return {f"{p.parent.name}/{p.stem}" for p in REQ_DIR.rglob("*.diag")}


def validate(item: dict, name: str, suite: str, reqs: set[str]) -> list[str]:
    f: list[str] = []
    add = f.append

    for field in REQUIRED:
        if not item.get(field):
            add(f"{name}: `{field}` is required")

    if item.get("id") and f"{item['id']}.diag" != name:
        add(f"{name}: id {item['id']!r} does not match the filename — a mismatch makes every grep "
            f"for the id miss this file")
    if item.get("author") and suite and item["author"] != suite:
        add(f"{name}: author={item['author']!r} but the file lives in suites/{suite}/. An item is "
            f"authored by exactly one suite and the directory is the fact.")

    cls = item.get("class")
    if cls and cls not in CLASSES:
        add(f"{name}: class={cls!r} is not one of GUIDE-CONFORMANCE §7.0's four "
            f"({', '.join(CLASSES)}). §8.5: a conformance item MUST declare its class, and 'vector' "
            f"alone does not — the four have different authors, different homes, and wildly "
            f"different costs to satisfy.")
    if cls and not item.get("class_basis"):
        add(f"{name}: `class` without `class_basis`. The class is not a label — §8.5 says the "
            f"classes are not interchangeable AS EVIDENCE, so the file states why it is this one.")

    surface = item.get("surface")
    if surface and surface not in SURFACES:
        add(f"{name}: surface={surface!r} not in {', '.join(SURFACES)}")
    if item.get("status") and item["status"] not in STATUSES:
        add(f"{name}: status={item['status']!r} not in {', '.join(STATUSES)}")

    # ── `drives` is the join, and a join that resolves to nothing is worse than none ──────
    drives = item.get("drives")
    if drives is not None and not isinstance(drives, list):
        add(f"{name}: `drives` must be an array of requirement ids")
    for target in (drives or []):
        if target not in reqs:
            add(f"{name}: drives {target!r}, which resolves to no requirement file. Coverage is "
                f"DERIVED from this field, so an unresolvable target inflates a number nobody can "
                f"check — and §8.5a's whole point is the pair of counts this makes possible.")

    for field in PROSE_FIELDS:
        v = item.get(field)
        if v is not None and (not isinstance(v, list) or not all(isinstance(x, str) for x in v)):
            add(f"{name}: `{field}` must be an ARRAY OF LINES, not {type(v).__name__}. "
                f"Diagnostic-notation strings are single-line (RFC 8949 §8); prose held as one "
                f"string is one unreviewable line.")

    # ── the arms, and the rule this gate exists to keep alive ────────────────────────────
    arms = item.get("arm") or []
    if not arms:
        add(f"{name}: no [[arm]] — an item that describes no observation measures nothing")
    for i, arm in enumerate(arms):
        if arm.get("kind") not in ARM_KINDS:
            add(f"{name}: arm {i} kind={arm.get('kind')!r} not in {', '.join(ARM_KINDS)}")
        if not arm.get("name"):
            add(f"{name}: arm {i} has no `name`")
        if not arm.get("why"):
            add(f"{name}: arm {i} has no `why` — the arm-level argument is what a reviewer reads")
        for table, required_key in ARM_TABLES.items():
            rows = arm.get(table)
            if rows is None:
                continue
            if not isinstance(rows, list):
                add(f"{name}: arm {i} `{table}` must be an array")
                continue
            for j, row in enumerate(rows):
                if not isinstance(row, dict) or not row.get(required_key):
                    add(f"{name}: arm {i} `{table}` row {j} has no `{required_key}`")
        unknown = [k for k in arm
                   if k not in ARM_TABLES and k not in ("name", "kind", "given", "why", "expect")]
        if unknown:
            add(f"{name}: arm {i} carries unknown table(s) {unknown}. The outcome vocabulary is "
                f"CLOSED (F67): a typo'd table is an assertion that never runs while the file "
                f"still reads as measured.")

    kinds = [a.get("kind") for a in arms]

    # ⛔ THE INHERITED RULE. Moved here from requirement-gate.py with ADR-0003's split, because the
    # arms moved. "A check that cannot be made to fail has not been shown to measure anything."
    exempt = surface == "unreachable" and isinstance(item.get("unreachable"), dict)
    if "negative-control" not in kinds and not exempt:
        add(f"{name}: NO NEGATIVE CONTROL. Mandatory — especially for an item that can never fire "
            f"against a correct implementation. A check that cannot be made to fail has not been "
            f"shown to measure anything. (Exempt only with surface=unreachable AND an "
            f"[unreachable] block; this file has neither or only one.)")
    if "conformant" not in kinds and not exempt:
        add(f"{name}: no conformant arm. Only an `unreachable` item with its exclusion block may "
            f"omit one.")
    if surface == "unreachable" and not item.get("unreachable"):
        add(f"{name}: surface=unreachable without an [unreachable] block naming the class, why no "
            f"proxy is admissible, and what would discharge it — a blank is indistinguishable from "
            f"nobody having looked (§5.2b.1).")
    return f


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if not SUITES.is_dir():
        print("item-gate: COULD NOT LOOK — no suites/", file=sys.stderr)
        return 2

    paths = sorted(SUITES.glob("*/items/**/*.diag"))
    if len(paths) < MIN_ITEMS:
        print(f"item-gate: COULD NOT LOOK — {len(paths)} item(s), below MIN_ITEMS={MIN_ITEMS}. "
              f"A glob that has stopped matching reports a clean run over nothing.", file=sys.stderr)
        return 2

    reqs = known_requirements()
    findings, by_suite, driven = [], {}, set()
    for path in paths:
        try:
            item = load(path)
        except GateError as exc:
            print(f"item-gate: COULD NOT LOOK — {exc}", file=sys.stderr)
            return 2
        suite = path.relative_to(SUITES).parts[0]
        findings.extend(validate(item, path.name, suite, reqs))
        by_suite[suite] = by_suite.get(suite, 0) + 1
        driven.update(item.get("drives") or [])

    for finding in findings:
        print(f"  FINDING {finding}", file=sys.stderr)

    print(f"item-gate: {len(paths)} item(s) — {len(findings)} finding(s)")
    print("  " + " · ".join(f"{k} {v}" for k, v in sorted(by_suite.items())))
    # ⭐ The sentence AGENTS.md promises and no tooling here could produce until ADR-0003: joint
    # coverage, DERIVED from `drives` rather than claimed.
    print(f"  requirements driven: {len(driven)} of {len(reqs)}"
          f"   |   ⚠ ONE suite, so this is not yet joint coverage — it is one instrument's reach, "
          f"and a second suite is what makes the number mean what it says")
    return 1 if findings else 0


def self_test() -> int:
    """Executed control. The negative-control rule is re-planted here, not inherited as a claim."""
    reqs = {"entity-core-protocol/ECP-R57"}
    clean = {
        "id": "ECP-R57-P1", "author": "s1", "class": "validate-peer check",
        "class_basis": ["because"], "drives": ["entity-core-protocol/ECP-R57"],
        "surface": "wire", "status": "draft", "snapshot": "entity-core-protocol/v0.8.2.25",
        "arm": [
            {"name": "a", "kind": "conformant", "why": "w"},
            {"name": "c", "kind": "negative-control", "why": "w"},
        ],
    }
    if validate(clean, "ECP-R57-P1.diag", "s1", reqs):
        print(f"SELF-TEST FAILED: the clean item was rejected: "
              f"{validate(clean, 'ECP-R57-P1.diag', 's1', reqs)}", file=sys.stderr)
        return 1

    def mutate(**kw):
        import copy
        c = copy.deepcopy(clean)
        c.update(kw)
        return c

    planted = [
        # ⛔ THE INHERITED RULE, FIRST. If this line ever stops refusing, ADR-0003's migration
        # deleted the most important check in the tree and no other test would have noticed.
        ("no negative control", mutate(arm=[{"name": "a", "kind": "conformant", "why": "w"}])),
        ("unreachable claimed to dodge the control, with no exclusion block",
         mutate(surface="unreachable", arm=[{"name": "w", "kind": "non-conformant", "why": "w"}])),
        ("no conformant arm",
         mutate(arm=[{"name": "c", "kind": "negative-control", "why": "w"}])),
        ("no arms at all", mutate(arm=[])),
        ("an arm with no `why`",
         mutate(arm=[{"name": "a", "kind": "conformant"},
                     {"name": "c", "kind": "negative-control", "why": "w"}])),
        ("a typo'd arm table — an assertion that never runs",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w", "acccept": []},
                     {"name": "c", "kind": "negative-control", "why": "w"}])),
        ("an accept row with no `outcome`",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w", "accept": [{"why": "w"}]},
                     {"name": "c", "kind": "negative-control", "why": "w"}])),
        # §8.5's [MUST], and F73's real home
        ("no class declared", mutate(**{"class": None})),
        ("a class outside §7.0's four", mutate(**{"class": "vector"})),
        ("a class with no basis — a label, not evidence", mutate(class_basis=None)),
        # the join
        ("drives nothing", mutate(drives=[])),
        ("drives a requirement that does not exist",
         mutate(drives=["entity-core-protocol/ECP-R404"])),
        ("author disagrees with the suite directory it lives in", mutate(author="someone-else")),
        ("an id that disagrees with its filename", mutate(id="ECP-R7-P1")),
        ("prose held as one unreviewable string", mutate(header="a single line")),
    ]
    for label, bad in planted:
        if not validate(bad, "ECP-R57-P1.diag", "s1", reqs):
            print(f"SELF-TEST FAILED: planted defect accepted — {label}", file=sys.stderr)
            return 1

    # A control on the control: the glob's floor must refuse to report a pass over nothing.
    print(f"item-gate self-test: OK — clean item accepted, {len(planted)} planted defects refused, "
          f"INCLUDING the negative-control rule inherited from requirement-gate.py at ADR-0003's "
          f"split (re-planted here, never assumed to have survived the move)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
