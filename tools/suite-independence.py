#!/usr/bin/env python3
"""No suite is in the reference oracle's language, and no suite reaches into another suite or tools/.

`AP-10`. Shared code is shared bugs; a shared language with the oracle is shared idioms and shared
libraries. Suite 1's first draft was Go, signed with the same `crypto/ed25519` as the oracle and the
reference peer, agreed with them beautifully **because it shared their habits**, and was thrown away.

⛔⭐ WHY THIS IS A TOOL AND WAS INLINE SHELL UNTIL 2026-09-17. Every other gate in this repo carries
planted controls and a `--self-test`. This one did not -- and on the day the first second suite
appeared it was edited, **silently stopped detecting anything, and reported a clean tree.** The
filter that removes a suite's self-references matched the `file:line:` prefix, which begins with
`suites/<n>/` on EVERY line, so it discarded the whole result set. A gate that passes because it
found nothing and a gate that passes because it looked at nothing print the same line.

⇒ **The gate with no negative control is the gate that broke.** That is this repo's own stage-6 rule
arriving from inside: *a check that cannot be made to fail has not been shown to measure anything.*

⚠ THE NEGATION CARVE-OUT, and its bound. A suite declaring WHAT IT DID NOT READ is doing the honest
thing, and `rs-conformance`'s module header does exactly that -- so a literal-path grep refused it,
in the one file where that declaration is most useful to a reviewer. Same shape as
`docs/SOURCES-CITATION-DEBT` on day one: *"a gate that punishes the honest act is a gate people route
around."* **Only a line carrying an explicit negation is exempt.** A suite QUOTING another suite's
design in a comment still trips: a comment cannot be a dependency, but it can be evidence of having
read one. Declaration-based and auditable, not tamper-proof -- the same posture as `PEERS.diag`
exclusions and `SOURCES.md` read-states.

Usage:  python3 tools/suite-independence.py [--self-test]
Exit:   0 clean · 1 finding · 2 could not look
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUITES = ROOT / "suites"

ORACLE_LANG = ("*.go", "go.mod", "go.sum")
# Build output and caches are not authored content. Their dependency files legitimately name paths
# the author never typed -- cargo writes absolute paths into `target/**/*.d` -- and treating a
# generated file as evidence about an author is simply wrong.
SKIP_DIRS = {"target", "__pycache__", "node_modules", ".git", "output", "dist", "build"}
SKIP_FILES = {"README.md"}
# How many preceding lines a negation marker may cover. A declaration is a short block; 4 is the
# span of rs-conformance's real one plus slack, and small enough that a leak below it still trips.
WINDOW = 4

REACH = re.compile(r"suites/[a-z0-9-]+/|\.\./\.\./tools/|(?:from|import)\s+tools")
NEGATION = re.compile(
    r"(did not|does not|do not|must not|never|not)\s+read|forbidden|not read|may not open",
    re.IGNORECASE)


def _files(suite_dir):
    for p in sorted(suite_dir.rglob("*")):
        if not p.is_file() or p.name in SKIP_FILES:
            continue
        if SKIP_DIRS & set(p.relative_to(suite_dir).parts):
            continue
        yield p


def scan(suites_root=SUITES):
    """-> (findings, n_suites). A finding is (suite, rel_path, lineno, line)."""
    if not suites_root.is_dir():
        return None, 0
    findings, n = [], 0
    for suite_dir in sorted(p for p in suites_root.iterdir() if p.is_dir()):
        n += 1
        name = suite_dir.name
        for f in _files(suite_dir):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                for m in REACH.finditer(line):
                    # ⛔ Compare the MATCH, never the line, and never the file path: every line of
                    # output from a recursive grep begins with `suites/<name>/`, which is what
                    # destroyed the shell version.
                    if m.group(0) == f"suites/{name}/":
                        continue
                    # ⚠ THE NEGATION IS A BLOCK, NOT A LINE, and assuming otherwise was the first
                    # bug in this rewrite. `rs-conformance`'s declaration puts "WHAT THIS SUITE DID
                    # NOT READ" on one line and the paths it did not read on the NEXT -- which is
                    # how a person writes a list and how nobody writes a dependency. So the window
                    # looks back a few lines. Bounded at WINDOW: a leak far below a declaration
                    # still trips, and the exemption cannot be claimed once for a whole file.
                    if any(NEGATION.search(x) for x in lines[max(0, i - 1 - WINDOW):i]):
                        continue
                    try:
                        where = str(f.relative_to(ROOT))
                    except ValueError:          # a self-test temp tree, not this repo
                        where = str(f)
                    findings.append((name, where, i, line.strip()[:160]))
                    break
    return findings, n


def oracle_language(suites_root=SUITES):
    hits = []
    for g in ORACLE_LANG:
        for p in suites_root.rglob(g):
            if SKIP_DIRS & set(p.relative_to(suites_root).parts):
                continue
            hits.append(str(p.relative_to(ROOT)))
    return sorted(hits)


# (name, file content, expect_finding)
CONTROLS = [
    ("a real leak in a comment trips",
     "// copied from suites/py-prototype/prototype/cbor.py\n", True),
    ("a real import trips", "from tools import cbordiag\n", True),
    ("a relative reach into tools/ trips", 'include!("../../tools/x")\n', True),
    ("a DID NOT READ declaration is exempt",
     "//! WHAT THIS SUITE DID NOT READ: `suites/py-prototype/**`, `suites/CONTROL-SET.diag`\n", False),
    ("a 'must not read' declaration is exempt",
     "# the brief says I must not read suites/py-prototype/prototype/cbor.py\n", False),
    ("a self-reference is exempt", "// see suites/SUITE/src/cbor.rs\n", False),
    ("an unrelated line is clean", "let x = 1;\n", False),
    # ⛔ The control that the shell version would have failed: a leak must still be found when the
    # file lives several directories deep, where the path prefix is longest.
    ("a leak deep in the tree still trips",
     "// suites/py-prototype/prototype/ed25519.py\n", True),
    # ⛔ The real shape from rs-conformance: the negation is on one line, the paths on the next.
    ("a MULTI-LINE did-not-read block is exempt",
     "//! WHAT THIS SUITE DID NOT READ, because that is the point:\n"
     "//! `suites/py-prototype/**`, `suites/*/items/**`, `suites/CONTROL-SET.diag`,\n"
     "//! and the 47 fused requirement files.\n", False),
    ("a leak FAR below a did-not-read block still trips",
     "//! WHAT THIS SUITE DID NOT READ: the other suite.\n" + "\n" * 9
     + "// copied from suites/py-prototype/prototype/cbor.py\n", True),
]


def self_test():
    import shutil
    import tempfile
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td) / "suites"
        for i, (name, content, expect) in enumerate(CONTROLS):
            shutil.rmtree(root, ignore_errors=True)
            deep = root / "SUITE" / "src" / "a" / "b"
            deep.mkdir(parents=True)
            (deep / "f.rs").write_text(content.replace("SUITE", "SUITE"))
            findings, _ = scan(root)
            got = bool(findings)
            if got != expect:
                print(f"  FAIL  {name}: expected finding={expect}, got {got} ({findings})",
                      file=sys.stderr)
                bad += 1
        # And the floor: a scan that cannot look must not report clean.
        shutil.rmtree(root, ignore_errors=True)
        if scan(root)[0] is not None:
            print("  FAIL  a missing suites/ directory did not report could-not-look",
                  file=sys.stderr)
            bad += 1
    if bad:
        print(f"suite-independence self-test: {bad} of {len(CONTROLS) + 1} control(s) FAILED",
              file=sys.stderr)
        return 1
    print(f"suite-independence self-test: OK — {len(CONTROLS)} planted control(s) held "
          "(a leak in a comment, a real import, a reach into tools/, a leak deep in the tree where "
          "the path prefix is longest — the case the shell version silently stopped catching — a "
          "leak far below a declaration, plus four declarations that must NOT trip including the "
          "MULTI-LINE block rs-conformance actually wrote), and an absent suites/ is could-not-look")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if not SUITES.is_dir():
        print(f"suite-independence: COULD NOT LOOK — no {SUITES}", file=sys.stderr)
        return 2
    go = oracle_language()
    if go:
        print("suite-independence: suite source in the reference oracle's language (Go) — AP-10:",
              file=sys.stderr)
        for p in go:
            print(f"  {p}", file=sys.stderr)
        return 1
    findings, n = scan()
    for suite, path, line, text in findings:
        print(f"  {suite} reaches outside itself\n      {path}:{line}: {text}", file=sys.stderr)
    if findings:
        print(f"suite-independence: {len(findings)} finding(s) — a suite referencing another suite "
              "or tools/. Sharing the SUBSTRATE is fine; sharing ASSERTIONS is not.", file=sys.stderr)
        return 1
    print(f"suite-independence: {n} suite(s); none in the oracle's language, none reaching into "
          "another suite or tools/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
