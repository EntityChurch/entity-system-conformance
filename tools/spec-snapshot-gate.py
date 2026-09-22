#!/usr/bin/env python3
"""spec-snapshot-gate — a pinned snapshot is pinned, or it is a copy that drifted.

    tools/spec-snapshot-gate.py              # verify every snapshot under spec-data/
    tools/spec-snapshot-gate.py --self-test  # plant the defects and require refusal

WHAT IT ASSERTS

Every directory under `spec-data/` carries a `MANIFEST.md` with a sha256 per document,
and every document's bytes hash to the digest recorded beside it. Nothing else.

WHY THIS RATHER THAN TRUST

A requirement is a claim about what a specification section requires, and it names the
snapshot it was read from. The snapshot's whole job is to make that claim re-checkable
later. **An edited snapshot does not announce itself** — the file still parses, the
citation still resolves, the requirement still reads as verified, and the one thing that
moved is the text nobody will re-read. `spec-data/README.md` states the rule; this is the
thing that can say it was broken.

The failure it is actually built for is the innocent one: someone re-syncs a snapshot in
place because upstream moved, which is exactly the operation the contract forbids and the
one a helpful agent performs without thinking. The remedy is a NEW snapshot directory.

THREE STATES, NOT TWO — the could-not-look rule (ADR-0012, GUIDE-CONFORMANCE §5.2b)

  clean            every digest matches                          exit 0
  findings         a digest moved, or a file is missing/extra    exit 1
  could-not-look   no snapshots, or a manifest with no digests   exit 2

A gate that examines zero things and prints a clean run is the defect this ecosystem has
shipped at least six times. **The count is printed and the floor is asserted.**
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DATA = ROOT / "spec-data"

# `| `FILE.md` | ... | `<64 hex>` |` — the MANIFEST table row. Deliberately loose about
# the middle columns (version headers move) and strict about the two that are the pin.
#
# `re.MULTILINE` IS LOAD-BEARING AND WAS MISSING ON THE FIRST RUN. Without it `^`/`$`
# anchor to the whole string, so this matched NOTHING against a real manifest — and the
# gate's own could-not-look arm is what reported it, in one line, on the first execution
# against real input. Kept in the comment rather than quietly corrected: an anchored
# pattern read against a multi-line file is a defect whose symptom is an empty result,
# and an empty result is indistinguishable from "the corpus is clean" in any gate that
# does not separate the two states. This one does, which is the only reason it was not
# a green run over zero rows.
#
# WIDENED 2026-09-12 FROM `*.md` TO ANY FILE, SUBDIRECTORIES INCLUDED. The ECF document declares its
# normative conformance contract to be a CBOR fixture (`ENTITY-CBOR-ENCODING` Appendix E), not prose.
# The first snapshot pinned the three `.md` documents and omitted it, and this gate could not have
# said so: a `.cbor` beside the documents was invisible to a `*.md` glob in BOTH directions -- never
# reported as unpinned, never verifiable if pinned. A snapshot's scope is "the normative text", and
# normative text is not a file extension.
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|.*\|\s*`?([0-9a-f]{64})`?\s*\|\s*$", re.MULTILINE)

# A path a pinned document NAMES as an artifact: backticked, with a directory component, and an
# artifact extension. Added 2026-09-12 (D13 / AP-2's second instance): the first snapshot was scoped by
# a document list, and ENTITY-CBOR-ENCODING names its normative conformance fixture by exactly this
# form — `test-vectors/ecf-conformance/conformance-vectors.cbor` — in a sentence nobody's pointer reached.
# Bare filenames are ignored (they restate a path named elsewhere); a directory-qualified artifact path
# that resolves to nothing pinned is a snapshot whose scope was set by the pointer, not by the content.
NAMED_ARTIFACT = re.compile(r"`((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.(?:cbor|diag|json|jsonl|toml))`")

# A floor on the corpus. The fragile part of this gate is a glob, and its failure mode is
# a clean run over nothing — which reads as "every snapshot verified".
MIN_SNAPSHOTS = 1


class GateError(Exception):
    """Could-not-look. Distinct from a finding, and it exits differently."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _where(path: Path) -> str:
    """Repo-relative where possible, absolute otherwise — the self-test runs outside the tree."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_manifest(manifest: Path) -> dict[str, str]:
    """filename -> recorded digest. Raises rather than returning empty."""
    pinned = {name: digest for name, digest in ROW.findall(manifest.read_text())}
    if not pinned:
        raise GateError(
            f"{_where(manifest)}: no digest rows. A manifest that records no "
            f"digest cannot fail, so the snapshot beside it is unpinned while looking pinned."
        )
    return pinned


def verify(snapshot: Path) -> list[str]:
    """Findings for one snapshot directory. Empty list is a clean verify."""
    manifest = snapshot / "MANIFEST.md"
    if not manifest.is_file():
        raise GateError(f"{_where(snapshot)}: no MANIFEST.md")

    pinned = parse_manifest(manifest)
    present = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob("*") if p.is_file()} - {"MANIFEST.md"}
    findings: list[str] = []

    for name in sorted(set(pinned) - present):
        findings.append(f"{snapshot.name}/{name}: pinned in MANIFEST.md, ABSENT from the snapshot")
    # An extra document is a finding, not a courtesy. A file nobody pinned is a file a
    # requirement can cite and nobody can re-verify.
    for name in sorted(present - set(pinned)):
        findings.append(f"{snapshot.name}/{name}: present, pinned by NOTHING in MANIFEST.md")

    # Every artifact a pinned document names must itself be pinned (D13).
    for doc in sorted(n for n in set(pinned) & present if n.endswith(".md")):
        for artifact in sorted(set(NAMED_ARTIFACT.findall((snapshot / doc).read_text()))):
            if artifact not in pinned:
                findings.append(
                    f"{snapshot.name}/{doc}: names `{artifact}`, which this snapshot does not pin. "
                    f"A document that names its normative artifact by path has put that artifact in "
                    f"scope; a snapshot of its prose alone is a snapshot scoped by a pointer (D13)."
                )

    for name in sorted(set(pinned) & present):
        actual = _sha256(snapshot / name)
        if actual != pinned[name]:
            findings.append(
                f"{snapshot.name}/{name}: DIGEST MOVED\n"
                f"    pinned {pinned[name]}\n"
                f"    actual {actual}\n"
                f"    A snapshot is never edited in place. If upstream moved, take a NEW "
                f"snapshot directory — every requirement citing this one was authored "
                f"against the pinned bytes and is now unverified, which is neither wrong "
                f"nor right."
            )
    return findings


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if not SPEC_DATA.is_dir():
        print("spec-snapshot-gate: COULD NOT LOOK — no spec-data/", file=sys.stderr)
        return 2

    # ADR-0001: a snapshot is `spec-data/<spec>/v<version>/`, two levels. Before 2026-09-15 it was
    # one — `spec-data/core-0.8.2.21/` — where `core` was an abbreviation this seat invented and
    # which collided with `core profile`, a real and different thing.
    #
    # An empty `<spec>/` is COULD NOT LOOK, never a clean run: a spec directory with no version in
    # it is exactly what a half-finished migration leaves behind, and this gate's whole failure mode
    # is a glob that has stopped matching reporting success over nothing.
    specs = sorted(p for p in SPEC_DATA.iterdir() if p.is_dir())
    snapshots = []
    for spec in specs:
        versions = sorted(p for p in spec.iterdir() if p.is_dir())
        if not versions:
            print(f"spec-snapshot-gate: COULD NOT LOOK — spec-data/{spec.name}/ holds no "
                  f"version directory. The layout is spec-data/<spec>/v<version>/.", file=sys.stderr)
            return 2
        snapshots.extend(versions)
    if len(snapshots) < MIN_SNAPSHOTS:
        print(
            f"spec-snapshot-gate: COULD NOT LOOK — {len(snapshots)} snapshot(s), below "
            f"MIN_SNAPSHOTS={MIN_SNAPSHOTS}. A glob that has stopped matching reports a "
            f"clean run over nothing.",
            file=sys.stderr,
        )
        return 2

    findings, documents = [], 0
    for snapshot in snapshots:
        try:
            findings.extend(verify(snapshot))
        except GateError as exc:
            print(f"spec-snapshot-gate: COULD NOT LOOK — {exc}", file=sys.stderr)
            return 2
        documents += len(parse_manifest(snapshot / "MANIFEST.md"))

    for finding in findings:
        print(f"  FINDING {finding}", file=sys.stderr)

    verb = "verified" if not findings else "checked"
    print(
        f"spec-snapshot-gate: {len(snapshots)} snapshot(s), {documents} document(s) {verb} "
        f"— {len(findings)} finding(s)"
    )
    return 1 if findings else 0


def self_test() -> int:
    """The executed control. A gate whose failure mode has never been demonstrated is not a gate."""
    import tempfile

    body = b"# A SPEC\n\n**Version**: 1.0\n"
    digest = hashlib.sha256(body).hexdigest()

    def build(tmp: Path, *, doc: bytes, row_digest: str, extra: bool = False,
              extra_binary: bool = False) -> Path:
        snap = tmp / "spec-data" / "probe-1.0"
        snap.mkdir(parents=True)
        (snap / "A-SPEC.md").write_bytes(doc)
        if extra:
            (snap / "UNPINNED.md").write_text("# nobody pinned me\n")
        if extra_binary:
            (snap / "vectors").mkdir()
            (snap / "vectors" / "fixture.cbor").write_bytes(b"\xa0")
        (snap / "MANIFEST.md").write_text(
            "# SNAPSHOT `probe-1.0`\n\n"
            "| File | Version header | sha256 |\n|---|---|---|\n"
            f"| `A-SPEC.md` | `1.0` | `{row_digest}` |\n"
        )
        return snap

    with tempfile.TemporaryDirectory() as d:
        clean = build(Path(d), doc=body, row_digest=digest)
        if verify(clean):
            print("SELF-TEST FAILED: the clean snapshot reported findings", file=sys.stderr)
            return 1

    # Each planted defect is one that a real, well-meaning edit produces — and whose
    # failure mode is a requirement that still reads as verified against text that moved.
    planted = [
        ("a document edited in place", dict(doc=body + b"\n**v1.1:** a clarification\n",
                                            row_digest=digest)),
        ("a document pinned but deleted", dict(doc=None, row_digest=digest)),
        ("a document present but pinned by nothing", dict(doc=body, row_digest=digest, extra=True)),
        # The case the `*.md` glob could not see: a normative fixture, in a subdirectory, unpinned.
        ("a non-markdown fixture in a subdirectory pinned by nothing",
         dict(doc=body, row_digest=digest, extra_binary=True)),
    ]
    for label, kw in planted:
        with tempfile.TemporaryDirectory() as d:
            doc = kw.pop("doc")
            snap = build(Path(d), doc=doc if doc is not None else body, **kw)
            if doc is None:
                (snap / "A-SPEC.md").unlink()
            if not verify(snap):
                print(
                    f"SELF-TEST FAILED: {label} verified clean. Its failure mode is a "
                    f"requirement that still cites this snapshot and is no longer "
                    f"re-checkable against it.",
                    file=sys.stderr,
                )
                return 1

    # D13, isolated: the document is pinned at its TRUE digest and names a fixture the snapshot never
    # took. The only admissible finding is the named-artifact one — a digest finding would pass this
    # control for the wrong reason, which is the defect a self-test exists to rule out.
    naming = body + b"\nThe conformance contract is `vectors/fixture.cbor`.\n"
    with tempfile.TemporaryDirectory() as d:
        snap = build(Path(d), doc=naming, row_digest=hashlib.sha256(naming).hexdigest())
        got = verify(snap)
        if len(got) != 1 or "names `vectors/fixture.cbor`" not in got[0]:
            print(f"SELF-TEST FAILED: a document naming an unpinned artifact path produced {got!r}; "
                  f"expected exactly the named-artifact finding (D13).", file=sys.stderr)
            return 1

    # The could-not-look arm: a manifest with no digest rows must NOT read as clean.
    with tempfile.TemporaryDirectory() as d:
        snap = Path(d) / "spec-data" / "probe-1.0"
        snap.mkdir(parents=True)
        (snap / "A-SPEC.md").write_bytes(body)
        (snap / "MANIFEST.md").write_text("# SNAPSHOT `probe-1.0`\n\nno table here\n")
        try:
            verify(snap)
        except GateError:
            pass
        else:
            print("SELF-TEST FAILED: a digest-free manifest verified clean", file=sys.stderr)
            return 1

    print(
        f"spec-snapshot-gate self-test: OK — clean snapshot accepted, "
        f"{len(planted) + 1} planted defects refused, could-not-look distinguished from clean"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
