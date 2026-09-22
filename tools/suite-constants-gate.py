#!/usr/bin/env python3
"""D16 / AP-13: a suite MUST NOT restate a spec-data/ snapshot as a constant.

    tools/suite-constants-gate.py              # check every suite source
    tools/suite-constants-gate.py --self-test  # the executed controls

WHY THIS EXISTS (F43, F65). A run-defining input that the requirement files already carry must be
DERIVED, never restated in suite source. A snapshot name in a suite is stamped into `spec.*` — the
verdict's comparability anchor — and stays correct only until the requirement set cites two
snapshots. It already cites two, mid-re-base, and always will once extensions land.

WHY IT IS A TOOL AND NOT A grep (2026-09-15, found by the ADR-0001 migration). The gate was a
Makefile one-liner anchored on `^NAME = "…snapshot…"` — a value beginning with a quote. It had two
defects, in OPPOSITE directions, and both survived every green run since D16 was ratified:

  * FALSE NEGATIVE — a path COMPOSED from segments evaded it entirely.
    `SNAP = ROOT / "spec-data" / "core-0.8.2.21"` sat in this suite's own tests, unseen.
    The regex measured one SPELLING of the defect, not the defect.
  * FALSE POSITIVE — `[^"']*` after a closing quote ran on into the trailing comment, so a line
    that merely MENTIONED a snapshot in prose was reported. Including, with some irony, the comment
    in run.py explaining why no such constant exists.

So it reads string literals properly: Python through `tokenize` (which yields literals and drops
comments by construction), other languages through a comment-stripping pass. A gate that reports a
comment teaches the next author to work around it, and a gate blind to a composed path was never
measuring the rule it was named for.
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DATA = ROOT / "spec-data"
SUITES = ROOT / "suites"
SUFFIXES = (".py", ".sh", ".rs", ".ts")

# `<spec>/v<version>` since ADR-0001. The version LEAF is the discriminating token: a literal
# holding just "v0.8.2.21" pins a snapshot as surely as the full path does.
LINE_COMMENT = re.compile(r"(?<![:\w])(#|//).*$")
STRINGS = re.compile(r"'([^'\\]*(?:\\.[^'\\]*)*)'|\"([^\"\\]*(?:\\.[^\"\\]*)*)\"")


def snapshot_tokens() -> list[str]:
    """Every name that pins a snapshot: the two-level path and its version leaf."""
    out = []
    for d in sorted(SPEC_DATA.glob("*/*/")):
        if not d.is_dir():
            continue
        out.append(f"{d.parent.name}/{d.name}")
        out.append(d.name)
    return out


def literals(path: Path, text: str) -> list[tuple[int, str]]:
    """(lineno, string-literal) for every literal in the file. Comments are never literals."""
    if path.suffix == ".py":
        try:
            toks = tokenize.generate_tokens(io.StringIO(text).readline)
            return [(t.start[0], t.string) for t in toks if t.type == tokenize.STRING]
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass  # fall through to the textual pass rather than reporting a clean file
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in STRINGS.finditer(LINE_COMMENT.sub("", line)):
            out.append((n, m.group(0)))
    return out


# ⛔⭐ BUILD OUTPUT IS NOT AUTHORED CONTENT, and this exclusion was added 2026-09-17, the day the
# first COMPILED suite appeared. `rs-conformance` derives its snapshot from the requirement files in
# a build script -- exactly what D16/AP-13 requires -- and cargo writes the DERIVED value into
# `target/**/out/snapshot.rs` as a string literal. This gate read that generated file and reported
# a hardcoded constant. ⚠ **It was flagging the correct implementation, for doing the right thing.**
#
# THIRD GATE IN ONE DAY WITH THIS ASSUMPTION (with lint-suite-independence and lint-ignored): every
# gate over `suites/**` was written when the only suite was hand-written Python, and silently
# assumed every file under it was typed by a person. **A compiled suite falsifies that**, and the
# assumption was invisible until one existed -- which is the whole argument for building a second
# suite rather than reasoning about one.
BUILD_DIRS = {"target", "__pycache__", "node_modules", "dist", "build", ".git", "out"}


def scan(tokens: list[str], root: Path = SUITES) -> list[str]:
    findings = []
    for path in sorted(p for p in root.rglob("*")
                       if p.suffix in SUFFIXES and p.is_file()
                       and not (BUILD_DIRS & set(p.relative_to(root).parts))):
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, lit in literals(path, text):
            for tok in tokens:
                if tok in lit:
                    rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
                    findings.append(
                        f"{rel}:{lineno}: string literal {lit} names the spec-data/ snapshot "
                        f"{tok!r}. Derive it from the requirement files this suite implements "
                        f"(D16/AP-13) — a constant here is correct only until the requirement "
                        f"set cites two snapshots.")
                    break
    return findings


def self_test() -> int:
    """Executed controls. Both directions, because this gate has been wrong in both."""
    import tempfile

    tokens = snapshot_tokens()
    if not tokens:
        print("suite-constants-gate: COULD NOT LOOK — no spec-data/<spec>/<version>/ snapshots",
              file=sys.stderr)
        return 2
    full = next(t for t in tokens if "/" in t)
    leaf = full.split("/")[1]

    planted = {
        # The form the old regex DID catch.
        "literal.py": f'SNAPSHOT = "{full}"\n',
        # The form it did NOT — this one was live in the tree.
        "composed.py": f'SNAP = ROOT / "spec-data" / "{full.split("/")[0]}" / "{leaf}"\n',
        # The leaf alone still pins a snapshot.
        "leaf.py": f'V = "{leaf}"\n',
        "composed.sh": f'SNAP="$REPO/spec-data/{full}"\n',
    }
    # Must NOT be reported: prose. The old gate reported these, which is how a gate teaches
    # people to route around it.
    clean = {
        "comment.py": f'X = "probe"  # declared unallocated at {full}; re-check at each re-take\n',
        "docstring_free.py": f'# There is deliberately NO SNAPSHOT = "{full}" constant here.\n',
        "derived.py": 'SNAP = ROOT / "spec-data" / snapshot_from_requirements()\n',
        "comment.sh": f'# pinned at {full}\nSNAP="$(cat .snap)"\n',
    }

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        for name, body in planted.items():
            (base / name).write_text(body)
        got = scan(tokens, base)
        for name in planted:
            if not any(name in g for g in got):
                print(f"SELF-TEST FAILED: {name} was not refused. The gate is measuring one "
                      f"spelling of the defect, not the defect.", file=sys.stderr)
                return 1
        for name in planted:
            (base / name).unlink()
        for name, body in clean.items():
            (base / name).write_text(body)
        got = scan(tokens, base)
        if got:
            print(f"SELF-TEST FAILED: prose was reported as a constant — {got}. A gate that "
                  f"reports a comment teaches the next author to work around it.", file=sys.stderr)
            return 1

    print(f"suite-constants-gate self-test: OK — {len(planted)} planted defect(s) refused "
          f"(literal, composed, leaf-only, shell), {len(clean)} prose mention(s) allowed")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    tokens = snapshot_tokens()
    if not tokens:
        print("suite-constants-gate: COULD NOT LOOK — no spec-data/<spec>/<version>/ snapshots",
              file=sys.stderr)
        return 2
    if not SUITES.is_dir() or not any(SUITES.iterdir()):
        print("suite-constants-gate: COULD NOT LOOK — no suites/", file=sys.stderr)
        return 2
    findings = scan(tokens)
    for f in findings:
        print(f"  FINDING {f}", file=sys.stderr)
    n = len(list(SUITES.glob("*/")))
    print(f"suite-constants-gate: {n} suite(s), {len(tokens) // 2} snapshot(s) — "
          f"{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
