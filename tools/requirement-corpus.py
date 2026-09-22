#!/usr/bin/env python3
"""Build the canonical requirement corpus and its ONE content digest.

    tools/requirement-corpus.py --out output/requirement-corpus.cbor
    tools/requirement-corpus.py --digest      # print the digest only
    tools/requirement-corpus.py --self-test

WHAT THIS REPLACES, and why it is the point of the format move. `DESIGN-THE-SUITE-CONTRACT` §2 asks
for a **comparability anchor** — a value that says two verdicts measured the same requirements.
Until 2026-09-15 we did not have one: `make build` sha256'd each TOML file separately and the "set
digest" was a dict of per-file digests, which is a manifest, not an identity. **Two runs could not
be compared by looking at one value.** A canonical CBOR build is that value. Because canonical CBOR
sorts map keys by encoded bytes, the digest is a function of CONTENT ALONE — reordering fields in a
`.diag` file, or reordering the files themselves, does not move it. That property is asserted in the
self-test, because it is the only thing that makes the number mean what it claims.

⛔ WHAT THIS VALUE IS NOT, and the name was wrong until 2026-09-15 (b). This is the digest of the
WHOLE CORPUS. It is `requirement_corpus_digest`. It was printed as `requirement_set_digest`, which
is the name of a different quantity: the per-RUN anchor over **the exact requirements a run
asserted**, computed by the instrument (`suites/py-prototype/run.py:anchor_field`) under
`GUIDE-CONFORMANCE` §3.1 item 7 — *"a verdict is the check-set actually asserted, never a proxy for
it."* Three values, three names, and they are not interchangeable:

    requirement_corpus_digest   all 50 .diag files        this file          "what corpus exists"
    implemented_set_digest      what a bundle implements  tools/build-info   "what this build can run"
    requirement_set_digest      what a RUN asserted       the instrument     "what this number means"

⚠ **ADR-0002 cites §5.1 as the authority and that citation is wrong** — §5.1 is a naming-and-citation
rule for a committed FIXTURE corpus, and adopting it imports §5.1b–d, two of which our `output/`
policy makes unbuildable (`entity-system-generator`, 2026-09-15, `GC-1`). The clause this corpus is
actually accountable to is §3.1 item 7. ADR-0002's citation is not corrected here because an ADR is
a record of a decision; the correction is carried in `TRACKER-entity-system-generator.md` and is owed
a superseding note. **The naming defect above is exactly the mechanism that clause bans — a value
under another value's name — and we shipped it for one day.**

The corpus is a build artifact under `output/`, not source: it is derived from the `.diag` files by
a deterministic function, exactly as `conformance-vectors.cbor` is derived from its `.diag`.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # __pycache__ is .gitignore'd; lint-ignored refuses it (AP-8)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REQ_DIR = ROOT / "requirements"
MIN_REQUIREMENTS = 5


def load_corpus(req_dir: Path = REQ_DIR) -> dict:
    """{ "<spec>/<stem>": <requirement map> } — the key is the path, so the mirror is IN the digest.

    Keying by id alone would make two requirements with the same id in different spec directories
    collide silently; keying by path means moving a file changes the corpus identity, which is
    correct — it IS a different corpus."""
    corpus = {}
    for path in sorted(req_dir.rglob("*.diag")):
        rel = path.relative_to(req_dir)
        corpus[rel.with_suffix("").as_posix()] = cbordiag.parse(path.read_text())
    return corpus


def build(req_dir: Path = REQ_DIR) -> tuple[bytes, str, int]:
    corpus = load_corpus(req_dir)
    if len(corpus) < MIN_REQUIREMENTS:
        raise SystemExit(f"requirement-corpus: COULD NOT LOOK — {len(corpus)} requirement(s), "
                         f"below MIN_REQUIREMENTS={MIN_REQUIREMENTS}. A glob that has stopped "
                         f"matching would otherwise publish a digest over nothing.")
    raw = cbordiag.encode(corpus)
    return raw, hashlib.sha256(raw).hexdigest(), len(corpus)


def self_test() -> int:
    import tempfile

    a = '{ "id": "ECP-R1", "level": "MUST", "reading": [ "one", "two" ] }'
    # Same content, different authoring order and different whitespace/comments.
    b = '''/ a comment /
    {
      "reading": [ "one", "two" ],
      "level":   "MUST",
      "id":      "ECP-R1"
    }'''
    if cbordiag.encode(cbordiag.parse(a)) != cbordiag.encode(cbordiag.parse(b)):
        print("SELF-TEST FAILED: field order changed the canonical bytes. The digest would then "
              "measure typing order, not content, and two identical corpora would not compare "
              "equal.", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "entity-core-protocol"
        base.mkdir(parents=True)
        for i in range(MIN_REQUIREMENTS):
            (base / f"ECP-R{i + 1}.diag").write_text(
                '{ "id": "ECP-R%d", "reading": [ "x" ] }' % (i + 1))
        raw1, digest1, n = build(Path(d))
        if n != MIN_REQUIREMENTS:
            print(f"SELF-TEST FAILED: built {n} requirement(s), expected {MIN_REQUIREMENTS}",
                  file=sys.stderr)
            return 1
        # Re-authoring one file with different whitespace must NOT move the digest.
        (base / "ECP-R1.diag").write_text('{\n  "reading": [ "x" ],\n  "id": "ECP-R1"\n}\n')
        _, digest2, _ = build(Path(d))
        if digest1 != digest2:
            print("SELF-TEST FAILED: whitespace and field order moved the corpus digest. It is "
                  "supposed to be a CONTENT digest.", file=sys.stderr)
            return 1
        # Changing one character of content MUST move it.
        (base / "ECP-R1.diag").write_text('{ "id": "ECP-R1", "reading": [ "y" ] }')
        _, digest3, _ = build(Path(d))
        if digest1 == digest3:
            print("SELF-TEST FAILED: a content change did NOT move the corpus digest. An anchor "
                  "that cannot distinguish two corpora anchors nothing.", file=sys.stderr)
            return 1
        # RENAMING a file must move it too: the layout mirror is part of corpus identity.
        (base / "ECP-R1.diag").write_text('{ "id": "ECP-R1", "reading": [ "x" ] }')
        (base / "ECP-R1.diag").rename(base / "ECP-R99.diag")
        _, digest4, _ = build(Path(d))
        if digest1 == digest4:
            print("SELF-TEST FAILED: moving a requirement did not move the corpus digest.",
                  file=sys.stderr)
            return 1
        # And the artifact must decode back to what went in.
        (base / "ECP-R99.diag").rename(base / "ECP-R1.diag")
        raw5, digest5, _ = build(Path(d))
        if digest5 != digest1 or cbordiag.decode(raw5) != load_corpus(Path(d)):
            print("SELF-TEST FAILED: the built artifact does not decode back to the corpus",
                  file=sys.stderr)
            return 1

    print("requirement-corpus self-test: OK — the digest is invariant under field order, file "
          "order and whitespace, and moves on any content change or file rename; the artifact "
          "decodes back to the corpus")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    raw, digest, n = build()
    if "--digest" in argv:
        print(digest)
        return 0
    if "--out" in argv:
        out = Path(argv[argv.index("--out") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)
        print(f"requirement-corpus: {n} requirement(s) -> {out} "
              f"({len(raw)} bytes)\n  requirement_corpus_digest sha256:{digest}")
        return 0
    print(f"requirement-corpus: {n} requirement(s), {len(raw)} bytes\n"
          f"  requirement_corpus_digest sha256:{digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
