#!/usr/bin/env python3
"""requirement-gate — the requirement format, validated in one place.

    tools/requirement-gate.py              # validate every requirements/**/*.toml
    tools/requirement-gate.py --self-test  # plant the defects and require refusal

**The neutral half.** This file is the reference reading of the format and the validator every
suite's arm is checked against. A suite that cannot execute a verb these definitions use disagrees
**visibly, at the schema**, rather than by silently skipping a requirement it did not implement.

WHY EACH RULE IS HERE. Every one is either a rule this repo's charter states, or something batch 1
got wrong while being written. None is a style preference.

  * **a negative control is mandatory** — "a check that cannot be made to fail has not been shown
    to measure anything" (charter; GUIDE-CONFORMANCE §5.2a's corollary). Enforced, not remembered.
  * **`id_status` is one of three and each carries its own obligations.** `unallocated` exists
    because batch 1 found binding MUSTs with no §9 row (F4); the whole point is that the count is
    VISIBLE, and a file that forgets to declare its state silently rejoins the allocated ones.
  * **`disputed` requires the dispute** — shipping disputed is the behaviour we want; shipping the
    WORD without the question is a confident requirement wearing a hedge.
  * **`unreachable` requires its exclusion block** — §5.2b.1: a proxy that cannot fail the way the
    real case fails MUST NOT be recorded as covering it, and a blank is indistinguishable from
    nobody having looked.
  * **a prediction declares `if_false` as well as `if_true`** — otherwise it is retrofitted after
    the run, which is not a prediction.
  * **every `routed` / `snapshot` reference resolves** — a citation resolves or it is not a
    citation.

THE FLOOR IS ASSERTED. The fragile part of this gate is a glob; its failure mode is a clean run
over nothing, which reads as "every requirement is valid".
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = ROOT / "requirements"

LEVELS = ("MUST", "MUST NOT", "SHOULD", "SHOULD NOT", "MAY", "IMPL-DEFINED")  # §8.5a's closed six
SURFACES = ("wire", "host-seam", "offline", "cross-peer", "unreachable")
STATUSES = ("draft", "reviewed", "ratified", "disputed")
ID_STATUSES = ("allocated", "pending-split", "unallocated")
ARM_KINDS = ("conformant", "negative-control", "non-conformant")

# The arm's OUTCOME vocabulary, closed and gated from 2026-09-14 (F67).
#
# It was unvalidated until an author added `[[requirement.arm.inconclusive]]` to ECP-R7 and this gate
# reported 0 findings — a fourth outcome kind, invented mid-file, silently certified. The failure mode
# is not the new word: it is that `[[requirement.arm.acccept]]` would have passed too, and a typo'd
# assertion is an assertion that never runs while its file still reads as measured. That is `AP-8`'s
# family — a gate certifying something it does not look at — one table over.
#
# ⛔ AND THE VOCABULARY WAS ENUMERATED FROM THE CORPUS, NOT FROM THE AUTHOR'S MEMORY (AP-3).
# The first cut of this table listed four members and went red on 20 files: `assert` — the MOST USED
# form in the tree, 74 arms — was missing from it. `AP-3` is precisely "a rule stated over the cases
# its author had in mind; the gate went red on its own corpus and the GATE was wrong." It is recorded
# here because the fix took one minute and the lesson is the expensive part: a closed vocabulary is
# derived by counting, and a gate whose first run reds the corpus is reporting on itself.
#
#   step         — how the arm is driven. Needs `op`; nests inside the arm (Q2)
#   assert       — a predicate on a CAPTURED value: `capture` + `kind` (+ equals/not_equals/expect)
#   accept       — a permitted OUTCOME. One or more; the arm passes on any (Q2: a set, not one
#                  `expect`, because two conformant outcomes are often both permitted)
#   refuse       — an OUTCOME that fails the arm. Where the obligation actually bites
#   witness      — a FIELD recorded and never scored. Takes `field`, not `outcome`
#   inconclusive — ⭐ an OUTCOME the requirement deliberately declines to score, because an open
#                  question owns it. Added 2026-09-14 for ECP-R7 under core-0.8.2.24: `close` and
#                  `silence` are CQ-35's and CQ-34's, and this file must neither accept them (which is
#                  what the .21 text's "any non-200" did, silently pre-empting the ruling in the
#                  permissive direction) nor fail them (pre-empting it in the strict one). Yields
#                  INCONCLUSIVE, which the suite already reports and which is NOT a pass (ADR-0012).
#                  ⚠ THIS IS A FORMAT CHANGE and it restarts CQ-12's ratification clock — deliberately.
#
# `why` is NOT required on an individual row: the corpus carries 26 `assert` rows and one `accept` row
# without it, and reddening them would be this comment's own anti-pattern a second time. The arm-level
# `why` is required and that is where a reviewer reads the argument.
# ⛔ AND THE REQUIRED FIELD IS THE INTERSECTION ACROSS EVERY ROW, NOT THE MODE.
# Second miss in the same edit: `assert` was given `capture`, which is in 63 of its 74 rows and in the
# three most common shapes — and is absent from a bare state predicate (`kind = "connected"`,
# `kind = "inbound_execute_count_within_window", equals = 2`). Two negative controls went red for being
# correct. **`kind` is what every assert row carries.** Counting is not enough: take the INTERSECTION
# of fields present in every row, because the mode describes the common case and a gate must describe
# the whole corpus. `why` is deliberately NOT required even where it is currently universal — that is
# an accident of 50 files, not an earned rule, and the arm-level `why` is where the argument is read.
ARM_TABLES = {
    "step":         "op",
    "assert":       "kind",
    "accept":       "outcome",
    "refuse":       "outcome",
    "witness":      "field",
    "inconclusive": "outcome",
}
# ADDED 2026-09-12 (batch 3) — THE FIRST FIELD ADDED SINCE THE FORMAT'S FIRST CUT, AND IT RESTARTS
# CQ-12's RATIFICATION CLOCK ON PURPOSE. Batch 2 authored two MUSTs whose level was ARGUED from
# entailment rather than quoted from a keyword (F11) and said a third would make that a format change;
# batch 3's emitted-type-conformance file is it. A level stated only in prose is this seat's founding
# defect in a new place: a suite scoring an argued MUST as a failure is exercising an authority
# prohibition 2 says we do not have, and nothing machine-readable said which MUSTs those were.
# Absent = "keyword". "entailed" must carry its argument in `reading`, and the count is printed.
LEVEL_BASES = ("keyword", "entailed")

REQUIRED = ("title", "spec", "snapshot", "level", "surface", "status", "id_status")
ECP_ID = re.compile(r"^ECP-R([1-9][0-9]?|9[0-8])$")   # the allocated space: ECP-R1…ECP-R98

MIN_REQUIREMENTS = 5


class GateError(Exception):
    """Could-not-look — a corpus that cannot be read at all. Exits 2, never 1."""


def load(path: Path) -> dict:
    try:
        doc = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise GateError(f"{path.name}: not parseable — {exc}") from exc
    req = doc.get("requirement")
    if not isinstance(req, dict):
        raise GateError(f"{path.name}: no [requirement] table")
    return req


def validate(req: dict, name: str) -> list[str]:
    f: list[str] = []
    add = f.append

    for field in REQUIRED:
        if not req.get(field):
            add(f"{name}: [requirement].{field} is required")
    if not req.get("reading"):
        add(f"{name}: no `reading`. A requirement authored from the spec states the reading it "
            f"pins, so a reviewer checks the REQUIREMENT against the SPEC rather than against what "
            f"an implementation happens to do.")

    level, surface = req.get("level"), req.get("surface")
    status, id_status = req.get("status"), req.get("id_status")
    basis = req.get("level_basis", "keyword")
    if basis not in LEVEL_BASES:
        add(f"{name}: level_basis={basis!r} not in {', '.join(LEVEL_BASES)}")
    elif basis == "entailed" and "ENTAIL" not in str(req.get("reading", "")).upper():
        add(f"{name}: level_basis=entailed but `reading` never argues the entailment. An entailed "
            f"level is one we ARGUED; the argument is the only thing that makes it reviewable.")
    if level and level not in LEVELS:
        add(f"{name}: level={level!r} is outside §8.5a's closed six ({', '.join(LEVELS)})")
    if surface and surface not in SURFACES:
        add(f"{name}: surface={surface!r} not in {', '.join(SURFACES)}")
    if status and status not in STATUSES:
        add(f"{name}: status={status!r} not in {', '.join(STATUSES)}")
    if id_status and id_status not in ID_STATUSES:
        add(f"{name}: id_status={id_status!r} not in {', '.join(ID_STATUSES)}")

    # ── the three id states, each with its own obligations ────────────────────────────────
    rid = req.get("id")
    if id_status == "allocated":
        if not rid or not ECP_ID.match(str(rid)):
            add(f"{name}: id_status=allocated needs an `id` inside the allocated space "
                f"ECP-R1…ECP-R98. Got {rid!r}. Arch fixed that space; a number outside it is one "
                f"we minted in their namespace.")
        elif f"{rid}.toml" != name:
            add(f"{name}: id {rid!r} does not match the filename. One requirement, one file, one "
                f"name — a mismatch makes every grep for the id miss this file.")
    elif id_status == "pending-split":
        if rid:
            add(f"{name}: a pending-split requirement MUST NOT carry an `id` — its number is "
                f"arch's to append from ECP-R99 when the §9 conversion lands (CQ-2).")
        if not req.get("under"):
            add(f"{name}: pending-split needs `under` — the §9 row whose bundle it belongs to")
        if not req.get("routed"):
            add(f"{name}: pending-split needs `routed`. A split is a FINDING; one carried privately "
                f"is a split performed here, which is the thing CQ-2 forbids.")
    elif id_status == "unallocated":
        if rid:
            add(f"{name}: an unallocated requirement MUST NOT carry an `id` — no §9 row exists for it")
        if not req.get("routed"):
            add(f"{name}: unallocated needs `routed`. Its whole value is that the COUNT is visible "
                f"and routed (F4); an unrouted one is a private opinion about the floor.")

    if status == "disputed" and not req.get("dispute"):
        add(f"{name}: status=disputed without a [requirement.dispute] block naming the question and "
            f"its owner. The word without the question is a confident requirement wearing a hedge.")
    if surface == "unreachable" and not req.get("unreachable"):
        add(f"{name}: surface=unreachable without a [requirement.unreachable] block. A declared "
            f"exclusion names the class, why no proxy is admissible, and what would discharge it — "
            f"a blank is indistinguishable from nobody having looked.")

    # ── arms: at least one conformant, EXACTLY the negative control that is mandatory ─────
    arms = req.get("arm") or []
    if not arms:
        add(f"{name}: no [[requirement.arm]] — a requirement that describes no observation "
            f"measures nothing")
    kinds = [a.get("kind") for a in arms]
    for i, arm in enumerate(arms):
        if arm.get("kind") not in ARM_KINDS:
            add(f"{name}: arm {i} kind={arm.get('kind')!r} not in {', '.join(ARM_KINDS)}")
        if not arm.get("name"):
            add(f"{name}: arm {i} has no `name`")
        if not arm.get("why"):
            add(f"{name}: arm {arm.get('name', i)!r} has no `why`. The why is what a reviewer "
                f"checks against the spec; without it the arm is an assertion nobody can audit.")
        # F67: the arm's table vocabulary is CLOSED, and an unknown key is refused rather than
        # ignored. An ignored `acccept` is an assertion that silently never runs, in a file that
        # still counts toward every number this gate prints.
        for key, val in arm.items():
            if not isinstance(val, list):
                continue
            required = ARM_TABLES.get(key)
            if required is None:
                add(f"{name}: arm {arm.get('name', i)!r} has table {key!r}, not in "
                    f"{', '.join(ARM_TABLES)}. An unrecognised table is SILENTLY NEVER EVALUATED "
                    f"while the file still reads as measured (F67).")
                continue
            for j, row in enumerate(val):
                if not isinstance(row, dict):
                    add(f"{name}: arm {arm.get('name', i)!r} {key}[{j}] is not a table.")
                elif not row.get(required):
                    add(f"{name}: arm {arm.get('name', i)!r} {key}[{j}] needs `{required}`.")
        # An arm that can only pass has not been shown to measure anything — the charter's rule 2,
        # applied to the arm rather than to the file. Scoped to OUTCOME-shaped conformant arms:
        # `assert`-shaped ones fail by their predicate, and the negative control is exempt BY
        # CONSTRUCTION, since its whole job is to fire on the conformant path.
        if (arm.get("kind") == "conformant" and arm.get("accept")
                and not arm.get("refuse") and not arm.get("assert")):
            add(f"{name}: conformant arm {arm.get('name', i)!r} declares `accept`, no `refuse` and "
                f"no `assert`. It cannot fail, so it measures nothing — name what the obligation "
                f"forbids.")
    # THE ONE EXEMPTION, AND IT WAS EARNED ON THE GATE'S FIRST REAL RUN (F8).
    #
    # "Every requirement has a negative control" is the charter's rule and it was written here
    # without a state for the requirement that HAS NO OBSERVATION. `ECP-R66-pending-d` — §4.10(a)'s
    # "the default maximum MUST be finite" — is unreachable by construction: no finite probe
    # separates "the bound is 2 GiB" from "there is no bound". A control is an observation that
    # must NOT fire, and a requirement with no admissible observation cannot have one.
    #
    # The exemption is narrow on purpose, because "declare unreachable and skip the control" is an
    # obvious loophole: it applies ONLY with surface=unreachable, which itself requires the
    # [requirement.unreachable] block naming the class, why no proxy is admissible, and what would
    # discharge it — and the gate PRINTS the unreachable count every run, so the exemption is
    # measured rather than merely permitted.
    exempt = surface == "unreachable" and isinstance(req.get("unreachable"), dict)
    if "negative-control" not in kinds and not exempt:
        add(f"{name}: NO NEGATIVE CONTROL. Mandatory — especially for a requirement that can never "
            f"fire against a correct implementation. A check that cannot be made to fail has not "
            f"been shown to measure anything. (Exempt only with surface=unreachable AND a "
            f"[requirement.unreachable] block; this file has neither or only one.)")
    if "conformant" not in kinds and not exempt:
        add(f"{name}: no conformant arm. Only an `unreachable` requirement with its exclusion "
            f"block may omit one.")

    # ── a prediction that cannot be wrong is not a prediction ────────────────────────────
    pred = req.get("predicted_disagreement")
    if pred:
        for field in ("against", "prediction", "basis", "if_true", "if_false"):
            if not pred.get(field):
                add(f"{name}: [requirement.predicted_disagreement] needs `{field}`. Without "
                    f"`if_false` in particular it is retrofitted after the run, which is not a "
                    f"prediction.")

    # ── citations resolve, or they are not citations ─────────────────────────────────────
    snap = req.get("snapshot")
    if snap and not (ROOT / "spec-data" / str(snap)).is_dir():
        add(f"{name}: snapshot={snap!r} names no directory under spec-data/. Every requirement "
            f"cites the text it was read from, or it cannot be re-verified when that text moves.")
    routed = req.get("routed")
    if routed:
        target = str(routed).split()[0].split("#")[0]
        if target.endswith(".md") and not (ROOT / target).is_file():
            add(f"{name}: routed={target!r} does not resolve")

    return f


# ── the executed-by-a-suite ratchet (D14, 2026-09-13) ─────────────────────────────────────────────
#
# Fifty requirement files were authored, reviewed and gated before one of them was run against a peer.
# The first run is what proved the format, the arms and the controls executable (AP-9). A requirement no
# suite implements is a claim nobody has tried to fail, so the count of them is printed every run and
# may only go DOWN: it is capped by requirements/UNEXECUTED-CEILING, which is lowered by hand when a
# suite implements more and never raised.
SUITES = ROOT / "suites"
CEILING = REQ_DIR / "UNEXECUTED-CEILING"


def implemented(suites: Path) -> dict[str, set[str]]:
    out = {}
    for manifest in sorted(suites.glob("*/IMPLEMENTS")):
        ids = {l.strip() for l in manifest.read_text().splitlines() if l.strip() and not l.startswith("#")}
        out[manifest.parent.name] = ids
    return out


def executed_findings(stems: set[str], impl: dict[str, set[str]], ceiling: int | None) -> tuple[list[str], int]:
    f = []
    for suite, ids in impl.items():
        for rid in sorted(ids - stems):
            f.append(f"suites/{suite}/IMPLEMENTS names {rid!r}, which is no requirement file — a suite "
                     f"claiming a requirement that does not exist reports coverage of nothing")
    unexecuted = len(stems - set().union(*impl.values())) if impl else len(stems)
    if ceiling is None:
        f.append(f"{CEILING.relative_to(ROOT)} missing or unreadable — the ratchet has no ceiling, so it cannot hold")
    elif unexecuted > ceiling:
        f.append(f"{unexecuted} requirement files are implemented by no suite, above the ceiling of {ceiling}. "
                 f"New requirements land WITH their suite implementation (D14); author less or implement more")
    return f, unexecuted


def read_ceiling() -> int | None:
    try:
        return int(next(l for l in CEILING.read_text().splitlines() if l.strip() and not l.startswith("#")))
    except (OSError, StopIteration, ValueError):
        return None


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if not REQ_DIR.is_dir():
        print("requirement-gate: COULD NOT LOOK — no requirements/", file=sys.stderr)
        return 2
    paths = sorted(REQ_DIR.rglob("*.toml"))
    if len(paths) < MIN_REQUIREMENTS:
        print(f"requirement-gate: COULD NOT LOOK — {len(paths)} file(s), below "
              f"MIN_REQUIREMENTS={MIN_REQUIREMENTS}. A glob that has stopped matching reports a "
              f"clean run over nothing.", file=sys.stderr)
        return 2

    findings, tally = [], {s: 0 for s in ID_STATUSES}
    disputed = unreachable = predictions = entailed = 0
    for path in paths:
        try:
            req = load(path)
        except GateError as exc:
            print(f"requirement-gate: COULD NOT LOOK — {exc}", file=sys.stderr)
            return 2
        findings.extend(validate(req, path.name))
        tally[req.get("id_status", "unallocated")] = tally.get(req.get("id_status"), 0) + 1
        disputed += req.get("status") == "disputed"
        unreachable += req.get("surface") == "unreachable"
        predictions += bool(req.get("predicted_disagreement"))
        entailed += req.get("level_basis") == "entailed"

    impl = implemented(SUITES)
    ceiling = read_ceiling()
    ex_findings, unexecuted = executed_findings({p.stem for p in paths}, impl, ceiling)
    findings.extend(ex_findings)

    for finding in findings:
        print(f"  FINDING {finding}", file=sys.stderr)

    print(f"requirement-gate: {len(paths)} requirement(s) — {len(findings)} finding(s)")
    # The counts are the point, not decoration: `unallocated` is the measure of how much of the
    # protocol's binding text sits outside the §9 inventory (F4), and it is reported every run.
    print(f"  allocated {tally.get('allocated', 0)} · pending-split "
          f"{tally.get('pending-split', 0)} · unallocated {tally.get('unallocated', 0)}"
          f"   |   disputed {disputed} · unreachable {unreachable} · predictions {predictions}"
          f" · entailed {entailed}")
    per_suite = " · ".join(f"{k} {len(v)}" for k, v in impl.items()) or "no suites"
    print(f"  executed by a suite: {len(paths) - unexecuted} of {len(paths)} ({per_suite})"
          f"   |   unexecuted {unexecuted} ≤ ceiling {ceiling}")
    return 1 if findings else 0


def self_test() -> int:
    """Executed control. Every planted defect is one batch 1 could have shipped."""
    clean = {
        "id": "ECP-R1", "id_status": "allocated", "title": "t", "spec": "s",
        "snapshot": "core-0.8.2.21", "level": "MUST", "surface": "wire", "status": "draft",
        "reading": "r",
        "arm": [
            {"name": "a", "kind": "conformant", "why": "w"},
            {"name": "c", "kind": "negative-control", "why": "w"},
        ],
    }
    if validate(clean, "ECP-R1.toml"):
        print(f"SELF-TEST FAILED: the clean requirement was rejected: "
              f"{validate(clean, 'ECP-R1.toml')}", file=sys.stderr)
        return 1

    def mutate(**kw):
        import copy
        c = copy.deepcopy(clean)
        c.update(kw)
        return c

    planted = [
        ("no negative control",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w"}]), "ECP-R1.toml"),
        ("an arm with no `why`",
         mutate(arm=[{"name": "a", "kind": "conformant"},
                     {"name": "c", "kind": "negative-control", "why": "w"}]), "ECP-R1.toml"),
        ("disputed with no dispute block", mutate(status="disputed"), "ECP-R1.toml"),
        ("unreachable with no exclusion block", mutate(surface="unreachable"), "ECP-R1.toml"),
        # The loophole, planted: unreachable is the ONE exemption from the negative control, so a
        # file claiming it without the block that justifies it must still be refused on both counts.
        ("unreachable claimed to dodge the control, with no exclusion block",
         mutate(surface="unreachable",
                arm=[{"name": "w", "kind": "non-conformant", "why": "w"}]), "ECP-R1.toml"),
        ("a pending-split carrying a minted id",
         mutate(id_status="pending-split", under="ECP-R66", routed="x"), "ECP-R66-pending-b.toml"),
        ("an unallocated requirement that was never routed",
         mutate(id=None, id_status="unallocated"), "UNALLOCATED-x.toml"),
        ("an id outside the allocated space", mutate(id="ECP-R400"), "ECP-R400.toml"),
        ("an id that disagrees with its filename", mutate(id="ECP-R2"), "ECP-R1.toml"),
        ("a snapshot that resolves to nothing", mutate(snapshot="core-9.9.9.9"), "ECP-R1.toml"),
        ("a prediction with no `if_false`",
         mutate(predicted_disagreement={"against": "x", "prediction": "p", "basis": "b",
                                        "if_true": "t"}), "ECP-R1.toml"),
        ("a level outside §8.5a's closed six", mutate(level="REQUIRED"), "ECP-R1.toml"),
        ("a level_basis outside keyword/entailed", mutate(level_basis="implied"), "ECP-R1.toml"),
        ("an entailed level whose reading argues nothing", mutate(level_basis="entailed"), "ECP-R1.toml"),
        # F67, planted three ways. The first is the real incident: a fourth outcome kind invented in a
        # file and certified clean. The second is the one that actually costs a run — a typo'd `accept`
        # that is silently never evaluated. The third is an arm with no way to fail.
        ("an arm outcome table outside the closed vocabulary",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w",
                      "accept": [{"outcome": "ok", "why": "w"}],
                      "refuse": [{"outcome": "bad", "why": "w"}],
                      "sometimes": [{"outcome": "x", "why": "w"}]},
                     {"name": "c", "kind": "negative-control", "why": "w"}]), "ECP-R1.toml"),
        ("a typo'd accept table, which would silently never be evaluated",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w",
                      "acccept": [{"outcome": "ok", "why": "w"}],
                      "refuse": [{"outcome": "bad", "why": "w"}]},
                     {"name": "c", "kind": "negative-control", "why": "w"}]), "ECP-R1.toml"),
        ("a conformant arm that accepts and can never refuse",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w",
                      "accept": [{"outcome": "ok", "why": "w"}]},
                     {"name": "c", "kind": "negative-control", "why": "w"}]), "ECP-R1.toml"),
        # The rule this one guards was WRONG on its first cut (`capture`, the mode) and reddened two
        # correct negative controls. It is planted so the corrected rule (`kind`, the intersection)
        # is shown able to fail rather than merely shown able to pass the corpus.
        ("an assert row with no `kind`",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w",
                      "assert": [{"capture": "x", "equals": 1}]},
                     {"name": "c", "kind": "negative-control", "why": "w"}]), "ECP-R1.toml"),
        ("a witness declared as an outcome instead of a field",
         mutate(arm=[{"name": "a", "kind": "conformant", "why": "w",
                      "accept": [{"outcome": "ok", "why": "w"}],
                      "refuse": [{"outcome": "bad", "why": "w"}],
                      "witness": [{"outcome": "x", "why": "w"}]},
                     {"name": "c", "kind": "negative-control", "why": "w"}]), "ECP-R1.toml"),
    ]
    for label, doc, fname in planted:
        doc = {k: v for k, v in doc.items() if v is not None}
        if not validate(doc, fname):
            print(f"SELF-TEST FAILED: {label} validated clean. Its failure mode is a requirement "
                  f"that reads as measured and is not.", file=sys.stderr)
            return 1

    # The ratchet, planted: a manifest naming a missing file, a count above the ceiling, a missing ceiling.
    stems = {"ECP-R1", "ECP-R2", "ECP-R3"}
    if executed_findings(stems, {"s": {"ECP-R1"}}, 2)[0]:
        print("SELF-TEST FAILED: the ratchet refused a count AT its ceiling", file=sys.stderr)
        return 1
    for label, impl, ceil in [("a manifest naming no file", {"s": {"ECP-R1", "ECP-R999"}}, 5),
                              ("unexecuted above the ceiling", {"s": {"ECP-R1"}}, 1),
                              ("no ceiling at all", {"s": {"ECP-R1"}}, None)]:
        if not executed_findings(stems, impl, ceil)[0]:
            print(f"SELF-TEST FAILED: {label} passed the executed ratchet", file=sys.stderr)
            return 1
    planted.append(("executed-ratchet (3)", None, None))

    print(f"requirement-gate self-test: OK — clean definition accepted, "
          f"{len(planted)} planted defects refused")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
