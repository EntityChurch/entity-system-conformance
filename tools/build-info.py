#!/usr/bin/env python3
"""Write the suite bundle's BUILD.json: what requirement text this instrument was built from.

    tools/build-info.py --req-dir requirements/entity-core-protocol --loader <path> \\
        --pyrt-sha256 <hex> --musl-image <ref> --out <bundle>/BUILD.json \\
        --requirements-out <bundle>/requirements.cbor  ECP-R1 ECP-R2 …
    tools/build-info.py --self-test

Every verdict must be able to say EXACTLY which requirement text it measured, or two reports cannot
be compared and a "conformance number" anchors on nothing ([ADR-0012]).

FIELDS, and which question each answers:

  requirement_digests       per file — provenance. "Which text was THIS row measured against?"
  requirement_snapshots     per file — the spec pin each requirement was authored against. A SET,
                            never a scalar: a run legitimately spans snapshots mid-re-base, and
                            always will once extensions land (F65 / AP-13 / D16).
  implemented_set_digest    the canonical-CBOR digest of the requirements this suite IMPLEMENTS.
                            Because canonical CBOR sorts map keys by encoded bytes, it is a function
                            of content alone. ⚠ This is a BUILD fact, not a run fact — see below.
  requirement_corpus_digest the same over the WHOLE corpus, so a verdict also says what fraction of
                            what corpus it covered.

⛔ WHY THIS FILE NO LONGER EMITS `requirement_set_digest`, AND WHY THE BUNDLE CARRIES THE CORPUS.

`GUIDE-CONFORMANCE` §3.1 *Run discipline* item 7 is the clause a published conformance number is
accountable to, and it is not the one ADR-0002 originally cited (§5.1, which is a naming rule for a
committed FIXTURE corpus — `entity-system-generator`, 2026-09-15, `GC-1`/`GC-2`):

    "A verdict is the check-set actually asserted — never a proxy for it. … A published number MUST
    be dual-anchored: the oracle commit AND a `check_set_digest` over the exact assertions in the
    run (count + content), both required; a match on only one is not a match."

A digest over the IMPLEMENTED set, stamped on a run that selected a strict subset (`-category`, a
single id), anchors the number on a set LARGER than the one asserted. That is the "tracks which
checks ran rather than what they assert" family the clause bans, arriving from the other direction.
It was declared as a known scope limit here on 2026-09-15 and called "the honest next step"; §3.7
makes it an unmet [MUST] rather than a TODO with a good reason.

So: `--requirements-out` writes the canonical CBOR of the implemented set into the bundle, and the
INSTRUMENT computes the per-selection digest at run time with the SUITE'S OWN codec. Two consequences
worth stating rather than discovering:

  1. The artifact is self-certifying — sha256 of the bytes IS `implemented_set_digest`.
  2. ⭐ The two-codec cross-check now runs on EVERY RUN instead of only in `make test`. tools/ wrote
     these bytes; the suite decodes and re-encodes them and must reproduce them exactly. A
     disagreement between the two canonical-CBOR implementations `lint-suite-independence` forbids
     sharing a line is the whole reason the second one is paid for — and until now nothing on the
     run path could surface one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # __pycache__ is .gitignore'd; lint-ignored refuses it (AP-8)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402  — tools' OWN codec; never the suite's

ROOT = Path(__file__).resolve().parent.parent


def suite_version() -> str:
    try:
        v = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    except OSError:
        v = ""
    return v or "dev"


def build_info(req_dir: Path, ids: list[str], runtime: dict) -> tuple[dict, bytes]:
    """Returns (BUILD.json content, the canonical CBOR of the implemented set).

    The bytes are the artifact the instrument re-derives its per-run anchor from; their sha256 is
    `implemented_set_digest`, so the pair cannot drift apart without the digest moving."""
    digests, snaps, selected = {}, {}, {}
    missing = []
    for rid in ids:
        f = req_dir / f"{rid}.diag"
        if not f.is_file():
            missing.append(rid)
            continue
        raw = f.read_bytes()
        digests[rid] = hashlib.sha256(raw).hexdigest()
        req = cbordiag.parse(raw.decode())
        snaps[rid] = req.get("snapshot", "undeclared")
        selected[f"{req_dir.name}/{rid}"] = req
    if missing:
        raise SystemExit(f"build-info: IMPLEMENTS names {len(missing)} requirement file(s) that do "
                         f"not exist: {', '.join(missing)}. A bundle built over a missing "
                         f"requirement reports a verdict on text nobody can produce.")

    set_bytes = cbordiag.encode(selected)
    set_digest = hashlib.sha256(set_bytes).hexdigest()
    corpus = {}
    for path in sorted((ROOT / "requirements").rglob("*.diag")):
        rel = path.relative_to(ROOT / "requirements").with_suffix("").as_posix()
        corpus[rel] = cbordiag.parse(path.read_text())
    corpus_digest = hashlib.sha256(cbordiag.encode(corpus)).hexdigest()

    return {
        "suite_version": suite_version(),
        "requirement_digests": digests,
        "requirement_snapshots": snaps,
        # ⛔ NOT `requirement_set_digest`. That name belongs to the per-RUN anchor the instrument
        # computes over the requirements it actually asserted (§3.1 item 7). Giving a build-time
        # value the run-time name is exactly the substitution that clause bans, and it is the same
        # mistake `entity-system-generator` is fixing on their own `corpus digest:` print line.
        "implemented_set_digest": f"sha256:{set_digest}",
        "implemented_set_size": len(selected),
        "requirement_corpus_digest": f"sha256:{corpus_digest}",
        "requirement_corpus_size": len(corpus),
        "runtime": runtime,
    }, set_bytes


def self_test() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        req = Path(d) / "entity-core-protocol"
        req.mkdir(parents=True)
        (req / "ECP-R1.diag").write_text('{ "id": "ECP-R1", "snapshot": "s/v1", "reading": ["x"] }')
        (req / "ECP-R2.diag").write_text('{ "id": "ECP-R2", "snapshot": "s/v2", "reading": ["y"] }')
        info, set_bytes = build_info(req, ["ECP-R1", "ECP-R2"], {})
        if sorted(info["requirement_snapshots"].values()) != ["s/v1", "s/v2"]:
            print(f"SELF-TEST FAILED: snapshots not derived per requirement: {info}", file=sys.stderr)
            return 1
        # A set digest that does not change when the SELECTION changes is not a set digest.
        one, _ = build_info(req, ["ECP-R1"], {})
        if one["implemented_set_digest"] == info["implemented_set_digest"]:
            print("SELF-TEST FAILED: selecting a different requirement set produced the same "
                  "set digest. The comparability anchor would then say two different runs are "
                  "comparable.", file=sys.stderr)
            return 1
        # ...and one that changes when only the ORDER changes is not a content digest.
        if (build_info(req, ["ECP-R2", "ECP-R1"], {})[0]["implemented_set_digest"]
                != info["implemented_set_digest"]):
            print("SELF-TEST FAILED: IMPLEMENTS ordering moved the set digest. It measures "
                  "content, not the order someone listed ids in.", file=sys.stderr)
            return 1
        # ⭐ The shipped artifact is SELF-CERTIFYING: its sha256 is the digest BUILD.json reports.
        # If these two can disagree, the instrument's per-run anchor is derived from bytes the
        # build did not vouch for, and the whole chain is decorative.
        if f"sha256:{hashlib.sha256(set_bytes).hexdigest()}" != info["implemented_set_digest"]:
            print("SELF-TEST FAILED: the requirements artifact's sha256 is not the digest "
                  "BUILD.json reports for the same set.", file=sys.stderr)
            return 1
        # The artifact must decode back to the requirements, not to something merely well-formed:
        # the instrument re-encodes a SUBSET of it, so a lossy artifact silently changes the anchor.
        back = cbordiag.decode(set_bytes)
        if sorted(back) != ["entity-core-protocol/ECP-R1", "entity-core-protocol/ECP-R2"] or \
                back["entity-core-protocol/ECP-R1"]["snapshot"] != "s/v1":
            print(f"SELF-TEST FAILED: the requirements artifact does not decode back to the "
                  f"selected requirements: {sorted(back)}", file=sys.stderr)
            return 1
        # A missing requirement is a hard stop, never a quietly smaller set.
        try:
            build_info(req, ["ECP-R1", "ECP-R404"], {})
        except SystemExit:
            pass
        else:
            print("SELF-TEST FAILED: a bundle was built over a requirement file that does not "
                  "exist.", file=sys.stderr)
            return 1
    print("build-info self-test: OK — snapshots derived per requirement, the set digest moves with "
          "the selection and not with its order, the shipped artifact is self-certifying and "
          "decodes back to the requirements, a missing requirement refuses the build")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    ap = argparse.ArgumentParser(prog="build-info", allow_abbrev=False)
    ap.add_argument("--req-dir", required=True)
    ap.add_argument("--loader", required=True)
    ap.add_argument("--pyrt-sha256", required=True)
    ap.add_argument("--musl-image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--requirements-out", required=True,
                    help="canonical CBOR of the implemented set, shipped in the bundle so the "
                         "instrument can compute a PER-RUN anchor over what it actually asserted")
    ap.add_argument("ids", nargs="+")
    a = ap.parse_args(argv)

    runtime = {"pyrt_sha256": a.pyrt_sha256,
               "musl_loader_sha256": hashlib.sha256(Path(a.loader).read_bytes()).hexdigest(),
               "musl_image": a.musl_image}
    info, set_bytes = build_info(Path(a.req_dir), a.ids, runtime)
    Path(a.requirements_out).write_bytes(set_bytes)
    info["requirements_artifact"] = Path(a.requirements_out).name
    Path(a.out).write_text(json.dumps(info, indent=2) + "\n")
    print(f"build-info: {info['implemented_set_size']} of {info['requirement_corpus_size']} "
          f"requirement(s)\n  implemented_set_digest {info['implemented_set_digest']}"
          f"\n  {Path(a.requirements_out).name}: {len(set_bytes)} bytes — the instrument re-derives "
          f"its per-run anchor from these with its OWN codec")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
