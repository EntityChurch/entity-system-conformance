#!/usr/bin/env python3
"""D17 / audit A6 pass C: you may not cite a document this seat has not read.

    tools/sources-gate.py              # check the inventory and every citation against it
    tools/sources-gate.py --self-test  # the executed controls

WHY THIS EXISTS. For four working sessions `AGENTS.md` cited `GUIDE-CONFORMANCE` §5.2b, §5.2d, §7a
and §7d while **nobody in this repo had opened the document**. Every citation was inherited from a
bring-up handoff and **every one of them was accurate** — so citation-checking would never have found
it. The defect was omission: §7.0's four conformance classes, §8.5's *declare your class* `[MUST]`
that 0 of 50 requirement files satisfy, §3.4, §2.4c, and 36 sibling guides nobody had listed.

**The audit's A3 is what this tool answers.** Every gate in this tree was green through all four
sessions and *none of them could have been otherwise*: they all measure content we produced, and
**nothing measured whether the inputs were read.** A gate cannot see an absence unless something
makes it look. So this one fails on an UNREAD document that we cite — not merely a missing one.

WHAT IT CHECKS

  1. Every inventory row carries a read state from the declared vocabulary.
  2. `read`/`partial` carries a date. Rule 1 of SOURCES.md: no date, no claim.
  3. A document our documents CITE has a row here at all. (SOURCES.md rule 3.)
  4. A cited document is not `unread`.
  5. A cited SECTION of a `partial` document is covered by its `read:` list — where `§7` covers
     `§7.0` and does NOT cover `§7a`, because a letter is a different section. That distinction is
     the exact shape of the original incident.

THE DEBT LEDGER, and why this gate is not simply red. Citations to unread material exist today and
are named in the handoff as the next session's work. Deleting them would destroy information; being
red forever would make `make lint` useless and teach people to skip it. So the count is a RATCHET,
exactly like `requirements/UNEXECUTED-CEILING` (D14): `docs/SOURCES-CITATION-DEBT` holds the ceiling,
the count is printed on every run, and it may only go DOWN. **The absence is now a value something
prints**, which is what audit A6 pass B asked for.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "docs" / "SOURCES.md"
DEBT = ROOT / "docs" / "SOURCES-CITATION-DEBT"

STATES = ("unread", "partial", "read")
PINNED_CORPUS = "scope: pinned-corpus"

# Where we look for citations: our own authored documents and the requirement corpus.
CITING_GLOBS = ("AGENTS.md", "README.md", "docs/*.md", "docs/adr/*.md",
                "requirements/README.md", "requirements/*/*.diag", "spec-data/README.md")
# Injected verbatim and not ours to edit; docs/status/ is immutable dated record.
CITING_EXCLUDE = ("AGENTS-STANDARD.md", "METHODOLOGY.md", "docs/SOURCES.md")

DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
SECTION = re.compile(r"§\s*([0-9]+(?:\.[0-9]+)*[a-z]?)")
ROW = re.compile(r"^\|(.+)\|\s*$")
# A document identifier: FOO-BAR.md or FOO-BAR, upper-case and hyphens, at least two segments.
DOCNAME = re.compile(r"\b([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)(?:\.md)?\b")


class Entry:
    def __init__(self, name: str, cell: str, line: int):
        self.name, self.cell, self.line = name, cell, line
        self.state = None
        self.date = None
        self.read_sections: list[str] = []
        self.unread_sections: list[str] = []
        self.pinned_corpus = PINNED_CORPUS in cell
        plain = re.sub(r"[*`⭐⛔]", "", cell).strip()
        if self.pinned_corpus:
            plain = plain.split("—", 1)[-1].strip()
        for s in STATES:
            if re.match(rf"^{s}\b", plain):
                self.state = s
                break
        m = DATE.search(plain)
        self.date = m.group(1) if m else None
        # `read:` may name §-sections (a spec or guide) or plain artefacts (a code tree has no §).
        # Both satisfy rule 2; only the first can be coverage-checked, and the gate says which.
        self.read_clause = ""
        for label, into in (("read:", self.read_sections), ("unread:", self.unread_sections)):
            m = re.search(rf"(?<!un){label}\s*([^;—]*)" if label == "read:" else rf"{label}\s*([^;—]*)",
                          plain)
            if m:
                if label == "read:":
                    self.read_clause = m.group(1).strip()
                seen = set()
                for s in _expand(m.group(1)):
                    if s not in seen:
                        seen.add(s)
                        into.append(s)


SEC_TOKEN = re.compile(r"[0-9]+(?:\.[0-9]+)*[a-z]?")
RANGE = re.compile(r"^([0-9][0-9.]*[a-z]?)\s*[-–]\s*([0-9][0-9.]*[a-z]?|[a-z])$")


def _expand(text: str) -> list[str]:
    """`§2.4a-c, §5.2-5.2d, §7a-7d, §7` -> every section each range names.

    All three range spellings appear in SOURCES.md and each expands differently. Getting this
    wrong is not cosmetic: an unexpanded `§5.2-5.2d` reports every `§5.2b` citation in the tree
    as a citation into unread material, which is a false alarm at exactly the scale that
    teaches people to ignore the gate.
    """
    out: list[str] = []
    for part in text.split(","):
        part = part.strip().replace("§", "").strip()
        if not part:
            continue
        m = RANGE.match(part)
        if m:
            lo, hi = m.group(1), m.group(2)
            out.append(lo)
            if len(hi) == 1 and hi.isalpha():          # 2.4a-c
                stem, first = lo[:-1], lo[-1]
                if first.isalpha():
                    out.extend(stem + chr(c) for c in range(ord(first), ord(hi) + 1))
                    continue
            out.append(hi)
            if hi.startswith(lo) and len(hi) == len(lo) + 1 and hi[-1].isalpha():   # 5.2-5.2d
                out.extend(lo + chr(c) for c in range(ord("a"), ord(hi[-1]) + 1))
            elif (lo[:-1] == hi[:-1] and lo[-1].isalpha() and hi[-1].isalpha()):    # 7a-7d
                out.extend(lo[:-1] + chr(c) for c in range(ord(lo[-1]), ord(hi[-1]) + 1))
            continue
        out.extend(SEC_TOKEN.findall(part))
    return out


def covers(read: list[str], cited: str) -> bool:
    """`7` covers `7.0`; `7` does NOT cover `7a`. A letter is a different section."""
    for r in read:
        if cited == r or cited.startswith(r + "."):
            return True
    return False


def parse_sources(text: str) -> list[Entry]:
    entries, section = [], ""
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            section = line
            continue
        m = ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 2 or set("".join(cells)) <= set("-: "):
            continue
        if cells[0].lower() in ("document", "what"):
            continue
        if not re.match(r"^#+ [2-4]\.", section):
            continue
        entries.append(Entry(cells[0], cells[-1], n))
    return entries


def inventory_findings(entries: list[Entry]) -> list[str]:
    f = []
    for e in entries:
        # `scope: pinned-corpus` IS a declared state: the text is pinned by digest and its
        # per-section read record lives in each requirement's own `spec` field, which
        # `make lint-spec-data` and `make lint-requirements` already gate. The exclusion is
        # declared here and reported on every run rather than left implicit.
        if e.pinned_corpus:
            continue
        if e.state is None:
            f.append(f"SOURCES.md:{e.line}: {e.name} has no read state. The vocabulary is "
                     f"{'/'.join(STATES)}, and an entry with no state is indistinguishable from "
                     f"nobody having looked.")
        elif e.state in ("read", "partial") and not e.date:
            f.append(f"SOURCES.md:{e.line}: {e.name} claims {e.state!r} with no date. Rule 1: no "
                     f"date, no claim.")
        elif e.state == "partial" and not e.read_clause:
            f.append(f"SOURCES.md:{e.line}: {e.name} is 'partial' but has no `read:` clause "
                     f"naming what was read. Rule 2: 'skimmed' is not a state.")
    return f


def citation_findings(entries: list[Entry], root: Path = ROOT) -> list[str]:
    """Documents we cite, checked against what we have read of them."""
    checked = {}
    for e in entries:
        if e.pinned_corpus:
            continue
        for m in DOCNAME.finditer(e.name):
            checked.setdefault(m.group(1), e)
    known = set()
    for e in entries:
        for m in DOCNAME.finditer(e.name):
            known.add(m.group(1))

    f = []
    for pattern in CITING_GLOBS:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            if any(rel.endswith(x) or rel == x for x in CITING_EXCLUDE):
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                for m in DOCNAME.finditer(line):
                    name = m.group(1)
                    # A citation of a governing document, or of one we have never inventoried.
                    if name not in known:
                        continue
                    e = checked.get(name)
                    if e is None:
                        continue
                    tail = line[m.end():m.end() + 60]
                    cited = SECTION.findall(tail[:tail.find(".") + 1] if False else tail)
                    if e.state == "unread":
                        f.append(f"{rel}:{n}: cites {name}, which SOURCES.md records as UNREAD. "
                                 f"A citation inherited rather than read is the configuration this "
                                 f"gate exists for (F68/AP-14).")
                        break
                    if e.state == "partial" and cited:
                        for c in cited:
                            if not covers(e.read_sections, c):
                                why = ("explicitly listed unread"
                                       if covers(e.unread_sections, c) else "not among the sections read")
                                f.append(f"{rel}:{n}: cites {name} §{c}, {why} "
                                         f"(read: {', '.join('§' + s for s in e.read_sections) or 'none'}). "
                                         f"§7 covers §7.0 and does not cover §7a.")
                        break
    return f


def debt_keys(findings: list[str]) -> set[str]:
    """The debt is WHAT we rely on unread, not how many times we mention it.

    Counting citation SITES was the first cut and it was wrong in a way that showed up within the
    hour: writing the status entry that *reports* the debt cited `GUIDE-CONFORMANCE` §7a three more
    times and the ratchet refused the commit. Describing a gap is the opposite of the failure mode
    this gate exists for — relying on material nobody read — so the metric is the set of distinct
    (document, section) pairs. Reading §7a still takes it to zero; citing a section we have not read
    still raises it. Only re-mentioning one is free, and it should be.

    The individual sites are still printed, because the sites are what you go and fix."""
    keys = set()
    for f in findings:
        m = re.search(r"cites ([A-Z][A-Z0-9-]+)(?: §([0-9][0-9.a-z]*))?", f)
        if m:
            keys.add(f"{m.group(1)}§{m.group(2)}" if m.group(2) else m.group(1))
    return keys


def read_debt() -> int | None:
    try:
        return int(DEBT.read_text().split("#")[0].strip())
    except (OSError, ValueError):
        return None


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if not SOURCES.is_file():
        print("sources-gate: COULD NOT LOOK — no docs/SOURCES.md", file=sys.stderr)
        return 2
    entries = parse_sources(SOURCES.read_text())
    if len(entries) < 10:
        print(f"sources-gate: COULD NOT LOOK — {len(entries)} inventory row(s) parsed. A table "
              f"that has stopped matching reports a clean run over nothing.", file=sys.stderr)
        return 2

    hard = inventory_findings(entries)
    debt_items = citation_findings(entries)
    ceiling = read_debt()

    for x in hard:
        print(f"  FINDING {x}", file=sys.stderr)
    for x in debt_items:
        print(f"  DEBT {x}", file=sys.stderr)

    skipped = sum(1 for e in entries if e.pinned_corpus)
    states = {s: sum(1 for e in entries if e.state == s) for s in STATES}
    print(f"sources-gate: {len(entries)} governing document row(s) — "
          f"read {states['read']} · partial {states['partial']} · unread {states['unread']}"
          f"   |   {skipped} pinned-corpus row(s) deliberately not citation-checked")

    if ceiling is None:
        print(f"  FINDING {DEBT.relative_to(ROOT)} missing or unreadable — the ratchet has no "
              f"ceiling, so it cannot hold", file=sys.stderr)
        return 1
    keys = debt_keys(debt_items)
    print(f"  relies on unread material: {len(keys)} distinct document/section(s) "
          f"over {len(debt_items)} citation site(s) — ceiling {ceiling}")
    if len(keys) > ceiling:
        print(f"  FINDING reliance on unread material rose to {len(keys)} distinct "
              f"document/section(s) ({', '.join(sorted(keys))}), above "
              f"{DEBT.relative_to(ROOT)}={ceiling}. Read the document or drop the citation; the "
              f"ceiling is lowered by hand and never raised.", file=sys.stderr)
        return 1
    return 1 if hard else 0


def self_test() -> int:
    """Executed controls. Each plants one defect this gate is the only thing that could catch."""
    ok_table = (
        "## 2. Normative\n"
        "| Document | Owner | Governs | Read state |\n|---|---|---|---|\n"
        "| `ENTITY-CORE-PROTOCOL.md` | x | y | scope: pinned-corpus — pinned, read by section |\n"
        "## 3. Governing guidance\n"
        "| Document | Owner | Read state |\n|---|---|---|\n"
        "| `GUIDE-CONFORMANCE.md` | arch | partial 2026-09-14 — read: §1, §2.4a-c, §5.2-5.2d, §7; unread: §7a-7d, §9 |\n"
        "| `GUIDE-CAPABILITIES.md` | arch | unread |\n"
        "| `AGENTS-STANDARD.md` | meta | read 2026-09-11 — whole |\n"
    )
    entries = parse_sources(ok_table)
    if len(entries) != 4:
        print(f"SELF-TEST FAILED: parsed {len(entries)} rows, expected 4. The table parser is the "
              f"fragile part and its failure mode is a clean run over nothing.", file=sys.stderr)
        return 1
    if inventory_findings(entries):
        print(f"SELF-TEST FAILED: the clean inventory was rejected: {inventory_findings(entries)}",
              file=sys.stderr)
        return 1

    g = next(e for e in entries if "CONFORMANCE" in e.name)
    # Every range spelling that appears in SOURCES.md, expanded and asserted. An unexpanded range
    # is a false alarm on every citation under it, which is how a gate gets ignored.
    for label, spec, want in [
        ("§2.4a-c expands to its letters", ["2.4a", "2.4b", "2.4c"], True),
        ("§5.2-5.2d expands to the numeric stem AND its letters", ["5.2", "5.2b", "5.2d"], True),
        ("§7a-7d is NOT read, so its letters stay uncovered", ["7a", "7b", "7d"], False),
    ]:
        for s in spec:
            if covers(g.read_sections, s) is not want:
                print(f"SELF-TEST FAILED: {label} — §{s} (read: {g.read_sections})", file=sys.stderr)
                return 1
    for label, cited, want in [
        ("§7 covers §7.0", "7.0", True),
        ("§7 does NOT cover §7a — a letter is a different section", "7a", False),
        ("a read section matches itself", "2.4b", True),
        ("an unlisted section is not covered", "9", False),
    ]:
        if covers(g.read_sections, cited) is not want:
            print(f"SELF-TEST FAILED: {label} (read: {g.read_sections})", file=sys.stderr)
            return 1

    planted = [
        ("a row with no read state",
         "## 3. G\n| Document | Owner | Read state |\n|---|---|---|\n| `GUIDE-X.md` | arch | probably fine |\n",
         "no read state"),
        ("a 'read' claim with no date",
         "## 3. G\n| Document | Owner | Read state |\n|---|---|---|\n| `GUIDE-X.md` | arch | read — whole |\n",
         "no date"),
        ("'partial' naming no sections",
         "## 3. G\n| Document | Owner | Read state |\n|---|---|---|\n| `GUIDE-X.md` | arch | partial 2026-09-14 — had a look |\n",
         "no `read:` clause"),
    ]
    for label, table, tell in planted:
        got = inventory_findings(parse_sources(table))
        if not any(tell in x for x in got):
            print(f"SELF-TEST FAILED: {label} passed the inventory check (got {got}). Its failure "
                  f"mode is an inventory that looks complete and records nothing.", file=sys.stderr)
            return 1

    # The citation half, against a throwaway tree: the incident itself, reproduced.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / "docs").mkdir()
        (base / "docs" / "SOURCES.md").write_text(ok_table)
        (base / "AGENTS.md").write_text(
            "We follow GUIDE-CONFORMANCE §2.4a when authoring.\n"      # read      -> clean
            "The classes are in GUIDE-CONFORMANCE §7.0.\n"             # 7 covers  -> clean
            "See GUIDE-CONFORMANCE §7d for the fourth class.\n"        # unread    -> DEBT
            "GUIDE-CAPABILITIES.md says so.\n"                          # unread doc-> DEBT
        )
        got = citation_findings(entries, base)
        if len(got) != 2:
            print(f"SELF-TEST FAILED: expected exactly 2 citation debts (§7d into an unread "
                  f"range, and an unread document), got {len(got)}: {got}", file=sys.stderr)
            return 1
        if not any("§7d" in x for x in got):
            print(f"SELF-TEST FAILED: the §7d citation — the ORIGINAL incident — was not caught: "
                  f"{got}", file=sys.stderr)
            return 1
        if len(debt_keys(got)) != 2:
            print(f"SELF-TEST FAILED: expected 2 distinct debts, got {debt_keys(got)}",
                  file=sys.stderr)
            return 1
        # Mentioning the SAME gap again must not raise the debt — otherwise reporting the debt
        # raises it, and the honest act is the one the gate punishes.
        (base / "AGENTS.md").write_text(
            (base / "AGENTS.md").read_text()
            + "As noted, GUIDE-CONFORMANCE §7d is unread, and GUIDE-CONFORMANCE §7d blocks us.\n")
        again = citation_findings(entries, base)
        if len(again) <= len(got):
            print("SELF-TEST FAILED: extra citation sites were not even counted as sites",
                  file=sys.stderr)
            return 1
        if debt_keys(again) != debt_keys(got):
            print(f"SELF-TEST FAILED: re-mentioning a known gap raised the DEBT "
                  f"({debt_keys(got)} -> {debt_keys(again)}). Describing a gap is the opposite of "
                  f"relying on it.", file=sys.stderr)
            return 1

    print(f"sources-gate self-test: OK — clean inventory accepted, {len(planted)} planted defect(s) "
          f"refused, section coverage verified (§7 covers §7.0, not §7a), and the original "
          f"incident (citing §7d of a partially-read guide) reproduced and caught")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
