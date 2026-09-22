#!/usr/bin/env python3
"""ecp-index — bind `ECP-R<n>` to the §9 row it names, mechanically, from the pinned snapshot.

    tools/ecp-index.py                 # print the index
    tools/ecp-index.py --emit PATH     # write requirements/ECP-INDEX.md
    tools/ecp-index.py --check         # assert the index on disk still matches the snapshot
    tools/ecp-index.py --self-test     # plant the defects and require refusal

WHAT THIS IS, AND WHAT IT IS NOT

`entity-system-architecture` allocated the core spec's requirement prefix as **`ECP`** and fixed the
allocation *before* the §9 conversion lands, precisely so downstream authors are not blocked:

    §9.1's 66 rows → ECP-R1…R66 · §9.2's 9 → R67…R75 · §9.3's 10 → R76…R85 · §9.4's 13 → R86…R98
    A row that bundles k obligations keeps its id for the FIRST; the other k-1 APPEND from R99.

    -- PROPOSAL-THE-CORE-TIER-HAS-98-OBLIGATIONS-AND-NOT-ONE-OF-THEM-HAS-A-NAME §2 (DRAFT)

**That rule is deterministic, so the mapping is derivable — and until the conversion lands the
mapping exists NOWHERE.** Without it, "bind `ECP-R66`" is an instruction nobody can execute without
counting 66 bullets by hand, and a hand count is the error this whole exercise is about.

⛔ **This is DERIVED, never authoritative.** It does not author the specification ([prohibition 2]);
it applies arch's published rule to a pinned snapshot and shows its work. When the conversion lands,
**the spec's own table is the authority and this file is deleted** — not reconciled, deleted. Until
then it is the input we owe arch for their conversion, and any disagreement shows up as a diff
against a table rather than as a surprise inside a requirement.

WHY IT ASSERTS THE COUNTS RATHER THAN TRUSTING THEM

The ids are positional. If §9.1 gains a row upstream, **every id after it silently means a different
obligation** — the failure mode is not an error, it is a requirement that cites a real id for the
wrong rule. So the counts arch allocated against (66 / 9 / 10 / 13) are asserted here, against the
snapshot's bytes, and a mismatch is a refusal rather than a warning.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = "entity-core-protocol/v0.8.2.21"
SPEC = ROOT / "spec-data" / SNAPSHOT / "ENTITY-CORE-PROTOCOL.md"
EMIT_DEFAULT = ROOT / "requirements" / "ECP-INDEX.md"

# (heading, next heading, level, first id) — the allocation arch fixed. `expected` is asserted.
SECTIONS = [
    ("9.1 MUST Implement",        "9.2 SHOULD Implement",       "MUST",          1,  66),
    ("9.2 SHOULD Implement",      "9.3 MAY Implement",          "SHOULD",       67,   9),
    ("9.3 MAY Implement",         "9.4 Implementation-Defined", "MAY",          76,  10),
    ("9.4 Implementation-Defined", "9.5 Core Type Floor",       "IMPL-DEFINED", 86,  13),
]

ROW = re.compile(r"^- (.+)$", re.MULTILINE)
SECTION_REF = re.compile(r"§[0-9]+(?:\.[0-9]+)*[a-z]?(?:\([a-z]\))?")

# A conjunction between two obligations is §8.5a's own bundling tell. **Heuristic, and labelled as
# one everywhere it appears** — it over-reports ordinary prose and under-reports a row that bundles
# without a conjunction. It orders reading; it never concludes.
BUNDLE_HINT = re.compile(r"(?<!\w)(?: and | plus |; )(?!\w*$)")


class IndexError_(Exception):
    pass


def rows_of(text: str, start: str, end: str) -> list[str]:
    body = text.split(f"### {start}", 1)
    if len(body) != 2:
        raise IndexError_(f"§{start} not found in the snapshot")
    body = body[1].split(f"### {end}", 1)[0]
    return [m.group(1).strip() for m in ROW.finditer(body)]


def title_of(row: str) -> str:
    """The row's own opening clause, verbatim-derived. Never a paraphrase."""
    text = row.split(" — ")[0].split(" -- ")[0]
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)          # unbold
    text = re.sub(r"\s*\((?:§|v7\.|0\.8\.)[^()]*\)\s*$", "", text).strip()
    return (text[:117] + "…") if len(text) > 118 else text


def build(text: str) -> list[dict]:
    out: list[dict] = []
    for start, end, level, first_id, expected in SECTIONS:
        rows = rows_of(text, start, end)
        if len(rows) != expected:
            raise IndexError_(
                f"§{start}: {len(rows)} rows, expected {expected}. **The ids are POSITIONAL** — "
                f"arch allocated ECP-R1…R98 against 66/9/10/13, so a count that has moved means "
                f"every id after the change now names a different obligation. Re-take the snapshot, "
                f"re-derive, and tell arch before authoring anything against it."
            )
        for offset, row in enumerate(rows):
            out.append({
                "id": f"ECP-R{first_id + offset}",
                "level": level,
                "section": f"§{start.split()[0]}",
                "title": title_of(row),
                "refs": sorted(set(SECTION_REF.findall(row)), key=lambda s: (len(s), s)),
                "chars": len(row),
                "bundle_hint": bool(BUNDLE_HINT.search(row)),
            })
    return out


def render(index: list[dict]) -> str:
    hinted = [r for r in index if r["bundle_hint"]]
    lines = [
        "# `ECP-R<n>` — the derived index",
        "",
        "**DERIVED, NOT AUTHORITATIVE. Generated by `tools/ecp-index.py` from "
        f"`spec-data/{SNAPSHOT}/ENTITY-CORE-PROTOCOL.md`.**",
        "",
        "`entity-system-architecture` allocated the prefix `ECP` and **fixed the allocation before "
        "the §9 conversion lands**, so downstream authoring is not blocked "
        "(`PROPOSAL-THE-CORE-TIER-HAS-98-OBLIGATIONS-AND-NOT-ONE-OF-THEM-HAS-A-NAME` §2). The rule "
        "is deterministic — ids in §9 document order, one per existing row, splits appended from "
        "`ECP-R99` and never inserted — so the mapping is derivable. **Until the conversion lands "
        "it exists nowhere else**, and a requirement that says *\"bind `ECP-R66`\"* is otherwise an "
        "instruction discharged by counting 66 bullets by hand.",
        "",
        "⛔ **When §9 carries its own table, that table is the authority and this file is DELETED** "
        "— not reconciled. It is scaffolding with an expiry date, and it is also the input we owe "
        "arch for the conversion, so a disagreement surfaces as a diff against a table rather than "
        "as a surprise inside a requirement.",
        "",
        "**The ids are positional.** If a §9 row is added or removed upstream, every id after it "
        "names a different obligation — which is not an error anyone sees, it is a correct-looking "
        "citation of the wrong rule. `tools/ecp-index.py` asserts the 66 / 9 / 10 / 13 counts "
        "against the snapshot's bytes and refuses rather than warns.",
        "",
        "## Counts",
        "",
        "| Section | Level | Ids | Rows |",
        "|---|---|---|---:|",
    ]
    for start, _end, level, first_id, expected in SECTIONS:
        lines.append(
            f"| §{start.split()[0]} | `{level}` | `ECP-R{first_id}`–`ECP-R{first_id + expected - 1}` "
            f"| {expected} |"
        )
    lines += [
        f"| **total** | | | **{len(index)}** |",
        "",
        "## Bundling — a reading order, not a verdict",
        "",
        f"**{len(hinted)} of {len(index)}** rows carry a conjunction or a semicolon between what may "
        "be two obligations. ⚠ **That is a heuristic and it is wrong in both directions** — it "
        "over-reports ordinary prose and cannot see a row that bundles without a conjunction. It "
        "orders the reading; **a bundled row is confirmed by reading it and is then ROUTED to arch "
        "as a finding, never split here** (`CQ-2`, confirmed).",
        "",
        "## The index",
        "",
        "| id | Level | § | Row (opening clause, derived) | Cites | ⚠ |",
        "|---|---|---|---|---|---|",
    ]
    for r in index:
        refs = " ".join(f"`{x}`" for x in r["refs"][:4]) or "—"
        flag = "•" if r["bundle_hint"] else ""
        title = r["title"].replace("|", "\\|")
        lines.append(f"| `{r['id']}` | {r['level']} | {r['section']} | {title} | {refs} | {flag} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    try:
        index = build(SPEC.read_text())
    except IndexError_ as exc:
        print(f"ecp-index: REFUSING — {exc}", file=sys.stderr)
        return 2

    if "--check" in argv:
        if not EMIT_DEFAULT.is_file():
            print(f"ecp-index: REFUSING — {EMIT_DEFAULT.name} is absent", file=sys.stderr)
            return 2
        if EMIT_DEFAULT.read_text() != render(index):
            print(
                "ecp-index: FINDING — requirements/ECP-INDEX.md does not match the snapshot. "
                "Every requirement citing an ECP id was authored against the committed index; "
                "regenerate deliberately and re-read what moved.",
                file=sys.stderr,
            )
            return 1
    elif "--emit" in argv:
        target = Path(argv[argv.index("--emit") + 1]) if argv[-1] != "--emit" else EMIT_DEFAULT
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(index))
        print(f"ecp-index: wrote {target.relative_to(ROOT)}")

    hinted = sum(r["bundle_hint"] for r in index)
    # Arch asked for this caveat to live in the OUTPUT and not only in the docs, and they are right:
    # a count printed beside a list reads as a result. Measured on ECP-R66 — the heuristic flagged it
    # for the WRONG conjunction and missed the fourth obligation entirely, which was found by reading
    # §4.10(a) whole. A bundling heuristic ORDERS THE READING; it does not find the bundles.
    print(
        f"ecp-index: {len(index)} rows — ECP-R1…ECP-R{len(index)} @ snapshot {SNAPSHOT}\n"
        f"  {hinted} rows carry a bundling hint — A READING ORDER, NEVER A RESULT. Measured wrong in\n"
        f"  both directions on ECP-R66: flagged for the wrong conjunction, blind to the real fourth\n"
        f"  obligation. Bundles are found by reading the section whole and are ROUTED, never split here."
    )
    return 0


def self_test() -> int:
    """The executed control: the positional-id hazard, planted."""
    head = "### 9.1 MUST Implement\n\n"
    body = "".join(f"- Row {i} (§1.{i})\n" for i in range(1, 67))
    tail = (
        "\n### 9.2 SHOULD Implement\n\n" + "".join(f"- S{i} (§2.{i})\n" for i in range(1, 10))
        + "\n### 9.3 MAY Implement\n\n" + "".join(f"- M{i} (§3.{i})\n" for i in range(1, 11))
        + "\n### 9.4 Implementation-Defined\n\n" + "".join(f"- I{i} (§4.{i})\n" for i in range(1, 14))
        + "\n### 9.5 Core Type Floor\n"
    )
    clean = head + body + tail

    index = build(clean)
    if len(index) != 98 or index[65]["id"] != "ECP-R66" or index[65]["level"] != "MUST":
        print("SELF-TEST FAILED: the clean corpus did not allocate 98 ids with R66 as §9.1's last",
              file=sys.stderr)
        return 1
    if index[66]["id"] != "ECP-R67" or index[66]["level"] != "SHOULD":
        print("SELF-TEST FAILED: §9.2 did not start at ECP-R67/SHOULD", file=sys.stderr)
        return 1

    # THE defect this tool exists to catch: a row inserted upstream shifts every later id, and
    # nothing downstream errors — the citations still resolve, to the wrong obligations.
    planted = [
        ("a row INSERTED into §9.1", head + "- An added row (§1.99)\n" + body + tail),
        ("a row REMOVED from §9.1", head + body.split("\n", 1)[1] + tail),
        ("§9.2 missing entirely", head + body + "\n### 9.5 Core Type Floor\n"),
    ]
    for label, corpus in planted:
        try:
            build(corpus)
        except IndexError_:
            continue
        print(f"SELF-TEST FAILED: {label} built clean. Its failure mode is a requirement citing a "
              f"real id for a different obligation — a correct-looking citation of the wrong rule.",
              file=sys.stderr)
        return 1

    print(f"ecp-index self-test: OK — 98 ids allocated, {len(planted)} positional-shift defects refused")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
