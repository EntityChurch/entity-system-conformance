#!/usr/bin/env python3
"""Write the suite bundle's BUILD.json: what requirement text this instrument was built from.

    tools/build-info.py --req-dir requirements/entity-core-protocol --loader <path> \\
        --pyrt-sha256 <hex> --musl-image <ref> --out <bundle>/BUILD.json  ECP-R1 ECP-R2 …
    tools/build-info.py --self-test

Every verdict must be able to say EXACTLY which requirement text it measured, or two reports cannot
be compared and a "conformance number" anchors on nothing ([ADR-0012]).

FIELDS, and which question each answers:

  requirement_digests       per file — provenance. "Which text was THIS row measured against?"
  requirement_snapshots     per file — the spec pin each requirement was authored against. A SET,
                            never a scalar: a run legitimately spans snapshots mid-re-base, and
                            always will once extensions land (F65 / AP-13 / D16).
  requirement_set_digest    ⭐ the COMPARABILITY ANCHOR `DESIGN-THE-SUITE-CONTRACT` §2 asks for, and
                            until 2026-09-15 we did not have one. The canonical-CBOR digest of the
                            requirements this suite implements. Because canonical CBOR sorts map
                            keys by encoded bytes, it is a function of content alone.
  requirement_corpus_digest the same over the WHOLE corpus, so a verdict also says what fraction of
                            what corpus it covered.

⚠ SCOPE, DECLARED. `requirement_set_digest` covers the set the suite IMPLEMENTS. A run that selects
a strict subset (`-category`, a single id) reports its selection separately; the anchor still names
the implemented set. Computing a per-selection digest inside the instrument needs a canonical
encoder in the suite — it has one, and wiring it is the honest next step, not something to claim
here.
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


def build_info(req_dir: Path, ids: list[str], runtime: dict) -> dict:
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

    set_digest = hashlib.sha256(cbordiag.encode(selected)).hexdigest()
    corpus = {}
    for path in sorted((ROOT / "requirements").rglob("*.diag")):
        rel = path.relative_to(ROOT / "requirements").with_suffix("").as_posix()
        corpus[rel] = cbordiag.parse(path.read_text())
    corpus_digest = hashlib.sha256(cbordiag.encode(corpus)).hexdigest()

    return {
        "suite_version": suite_version(),
        "requirement_digests": digests,
        "requirement_snapshots": snaps,
        "requirement_set_digest": f"sha256:{set_digest}",
        "requirement_set_size": len(selected),
        "requirement_corpus_digest": f"sha256:{corpus_digest}",
        "requirement_corpus_size": len(corpus),
        "runtime": runtime,
    }


def self_test() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        req = Path(d) / "entity-core-protocol"
        req.mkdir(parents=True)
        (req / "ECP-R1.diag").write_text('{ "id": "ECP-R1", "snapshot": "s/v1", "reading": ["x"] }')
        (req / "ECP-R2.diag").write_text('{ "id": "ECP-R2", "snapshot": "s/v2", "reading": ["y"] }')
        info = build_info(req, ["ECP-R1", "ECP-R2"], {})
        if sorted(info["requirement_snapshots"].values()) != ["s/v1", "s/v2"]:
            print(f"SELF-TEST FAILED: snapshots not derived per requirement: {info}", file=sys.stderr)
            return 1
        # A set digest that does not change when the SELECTION changes is not a set digest.
        one = build_info(req, ["ECP-R1"], {})["requirement_set_digest"]
        if one == info["requirement_set_digest"]:
            print("SELF-TEST FAILED: selecting a different requirement set produced the same "
                  "set digest. The comparability anchor would then say two different runs are "
                  "comparable.", file=sys.stderr)
            return 1
        # ...and one that changes when only the ORDER changes is not a content digest.
        if (build_info(req, ["ECP-R2", "ECP-R1"], {})["requirement_set_digest"]
                != info["requirement_set_digest"]):
            print("SELF-TEST FAILED: IMPLEMENTS ordering moved the set digest. It measures "
                  "content, not the order someone listed ids in.", file=sys.stderr)
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
          "the selection and not with its order, a missing requirement refuses the build")
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
    ap.add_argument("ids", nargs="+")
    a = ap.parse_args(argv)

    runtime = {"pyrt_sha256": a.pyrt_sha256,
               "musl_loader_sha256": hashlib.sha256(Path(a.loader).read_bytes()).hexdigest(),
               "musl_image": a.musl_image}
    info = build_info(Path(a.req_dir), a.ids, runtime)
    Path(a.out).write_text(json.dumps(info, indent=2) + "\n")
    print(f"build-info: {info['requirement_set_size']} of {info['requirement_corpus_size']} "
          f"requirement(s)\n  requirement_set_digest {info['requirement_set_digest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
