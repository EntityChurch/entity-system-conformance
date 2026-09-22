#!/usr/bin/env python3
"""ONE-SHOT: requirements/<spec>/*.toml -> *.diag (audit A8 component 4).

    tools/migrate-toml-to-diag.py --check    # convert in memory, prove equality, write nothing
    tools/migrate-toml-to-diag.py --write    # convert and write the .diag files

**Kept in the tree only until the next release cut**, like `requirements/ECP-INDEX.md`. Its value is
that it makes the claim *"this was a format change and no content moved"* CHECKABLE rather than
asserted: `--check` converts every file and then converts the result BACK, asserting deep equality
against `tomllib`'s own parse of the original. A migration that says it preserved everything and
cannot demonstrate it is the same shape of claim this seat exists to refuse.

TWO FIELDS CHANGE REPRESENTATION, deliberately, and nothing else does:

  * The leading `##` comment block becomes `header`, an array of lines. **In TOML it was a comment,
    and comments do not survive canonicalization** — it would have been absent from the digested
    artifact while still looking present in the source (audit A8 cost 1). It carries the batch, the
    floor row and the provenance, so it is content.
  * `reading` — the interpretation argument, and the actual deliverable of this repo — becomes an
    array of lines for the same reason plus a second one: **diagnostic-notation text strings are
    single-line** (RFC 8949 §8), so a 2,400-character argument would become one 2,400-character
    line. Per-line diffs are how the argument gets reviewed, and a format that destroys them costs
    more than it saves. Joining the array with "\\n" reconstructs the text exactly, and the digest
    covers the array.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

sys.dont_write_bytecode = True   # __pycache__ is .gitignore'd; lint-ignored refuses it (AP-8)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "requirements"
PROSE = ("header", "reading")


def header_lines(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if line.startswith("##"):
            out.append(line[2:].lstrip() if line[2:3] == " " else line[2:])
        elif line.strip() == "" and out:
            continue
        elif out:
            break
    while out and not out[-1].strip():
        out.pop()
    return out


def to_diag(path: Path) -> dict:
    text = path.read_text()
    req = tomllib.loads(text)["requirement"]
    out: dict = {}
    hdr = header_lines(text)
    if hdr:
        out["header"] = hdr
    for k, v in req.items():
        out[k] = v.rstrip("\n").split("\n") if k == "reading" and isinstance(v, str) else v
    return out


def back(doc: dict) -> dict:
    """The inverse, for the equality proof: drop `header`, rejoin `reading`."""
    out = {k: v for k, v in doc.items() if k != "header"}
    if isinstance(out.get("reading"), list):
        out["reading"] = "\n".join(out["reading"]) + "\n"
    return out


def main(argv: list[str]) -> int:
    write = "--write" in argv
    paths = sorted(REQ.rglob("*.toml"))
    if not paths:
        print("migrate: COULD NOT LOOK — no .toml requirement files", file=sys.stderr)
        return 2
    changed = 0
    for path in paths:
        original = tomllib.loads(path.read_text())["requirement"]
        doc = to_diag(path)

        # 1. The inverse must reproduce tomllib's own parse of the original, exactly.
        if back(doc) != original:
            diff = [k for k in set(back(doc)) | set(original)
                    if back(doc).get(k) != original.get(k)]
            print(f"MIGRATION FAILED: {path.name} does not round-trip. Fields that differ: {diff}",
                  file=sys.stderr)
            return 1
        # 2. The emitted diagnostic notation must re-parse to the same structure.
        rendered = cbordiag.emit(doc)
        if cbordiag.parse(rendered) != doc:
            print(f"MIGRATION FAILED: {path.name} does not survive emit->parse", file=sys.stderr)
            return 1
        # 3. And it must encode canonically and decode back.
        if cbordiag.decode(cbordiag.encode(doc)) != doc:
            print(f"MIGRATION FAILED: {path.name} does not survive canonical encode->decode",
                  file=sys.stderr)
            return 1
        # 4. The header must not have been silently dropped where one existed.
        if path.read_text().startswith("##") and not doc.get("header"):
            print(f"MIGRATION FAILED: {path.name} opens with a ## block that was not captured",
                  file=sys.stderr)
            return 1

        if write:
            target = path.with_suffix(".diag")
            target.write_text(rendered + "\n")
            path.unlink()
            changed += 1

    print(f"migrate: {len(paths)} requirement(s) converted and PROVEN equal "
          f"(toml -> diag -> toml is identity; emit/parse and canonical encode/decode round-trip)"
          + (f"; {changed} written, {changed} .toml removed" if write else "; nothing written"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
