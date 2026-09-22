"""The codec against the snapshot's ECF conformance corpus (ENTITY-CBOR-ENCODING Appendix E), before any peer.

Every one of the corpus's vectors is accounted for: run, or declared not-run with a reason in NOT_RUN. An
unaccounted vector fails the test, so a corpus that grows cannot silently outrun this suite.

The corpus's artifact is the .cbor (its CHANGELOG: "the one a conformance report cites"), loaded with this
suite's own decoder; its sha256 is checked against the snapshot MANIFEST first.
"""

import hashlib
import math
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prototype import cbor, ed25519, ident  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent.parent
CORPUS_REL = Path("test-vectors") / "ecf-conformance" / "conformance-vectors.cbor"


def _snapshots() -> list[Path]:
    """D16/AP-13: the snapshot is DERIVED from the requirement files this suite implements,
    never restated here. A constant would be correct only until the requirement set cites two
    snapshots — which it already does, mid-re-base, and always will once extensions land.

    This file held `SNAP = ROOT / "spec-data" / "core-0.8.2.21"` from D16's ratification until
    2026-09-15. The gate that exists to forbid exactly that could not see it: it anchored on a
    value starting with a quote, and this one is composed from path segments.
    """
    ids = [l.strip() for l in (HERE / "IMPLEMENTS").read_text().splitlines()
           if l.strip() and not l.startswith("#")]
    names, seen = [], set()
    for rid in ids:
        text = (ROOT / "requirements" / "entity-core-protocol" / f"{rid}.diag").read_text()
        m = re.search(r'"snapshot"\s*:\s*"([^"]+)"', text)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            names.append(m.group(1))
    snaps = [ROOT / "spec-data" / n for n in names if (ROOT / "spec-data" / n / CORPUS_REL).is_file()]
    if not snaps:
        raise AssertionError(
            f"COULD NOT LOOK — none of the snapshots cited by IMPLEMENTS ({names}) carries "
            f"{CORPUS_REL}. A corpus test with no corpus reports a clean run over nothing.")
    return snaps


SNAPS = _snapshots()

# id -> why it is not run. Empty is the goal; every entry is a claim someone can check.
NOT_RUN: dict[str, str] = {}

# F30: which bytes the corpus's signature.* vectors sign. Measured here, reported, never assumed.
SIGNATURE_MESSAGE_FOUND: dict[str, list[str]] = {}


def _load(snap: Path):
    raw = (snap / CORPUS_REL).read_bytes()
    vectors, findings = cbor.decode(raw)
    return raw, vectors, findings


def _same(a, b) -> bool:
    """Structural equality that keeps what Python's == loses: NaN == NaN, and -0.0 != 0.0."""
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or (a == b and math.copysign(1, a) == math.copysign(1, b))
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return a == b


class Corpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Every snapshot the implemented requirements cite, not one named here.
        cls.loaded = [(s, *_load(s)) for s in SNAPS]

    def test_artifact_is_the_pinned_one(self):
        for snap, raw, _, findings in self.loaded:
            with self.subTest(snapshot=snap.name):
                manifest = (snap / "MANIFEST.md").read_text()
                digest = hashlib.sha256(raw).hexdigest()
                self.assertIn(digest, manifest, "conformance-vectors.cbor does not match the snapshot MANIFEST")
                self.assertEqual(findings.tags, [])

    def test_every_vector_accounted_for(self):
        for snap, _, vectors, _ in self.loaded:
            with self.subTest(snapshot=snap.name):
                ids = [v["id"] for v in vectors]
                self.assertEqual(len(ids), len(set(ids)), "duplicate vector ids")
                ran = [i for i in ids if i not in NOT_RUN]
                print(f"\necf corpus @ {snap.relative_to(ROOT / 'spec-data')}: {len(ids)} vectors — "
                      f"{len(ran)} run, {len(NOT_RUN)} declared not-run", file=sys.stderr)
                self.assertEqual(set(NOT_RUN) - set(ids), set(), "NOT_RUN names vectors the corpus does not have")

    def test_vectors(self):
        for snap, _, vectors, _ in self.loaded:
            self._vectors(snap, vectors)

    def _vectors(self, snap, vectors):
        for v in vectors:
            vid, kind = v["id"], v["kind"]
            if vid in NOT_RUN:
                continue
            cat = vid.split(".")[0]
            with self.subTest(snapshot=snap.name, vector=vid):
                if kind == "decode_reject":
                    self._reject(v)
                elif cat == "content_hash":
                    inp = v["input"]
                    got = ident.content_hash(inp["type"], inp["data"], inp.get("format_code", 0))
                    self.assertEqual(got.hex(), v["canonical"].hex())
                elif cat == "peer_id":
                    inp = v["input"]
                    pid = ident.base58(ident.varint(inp["key_type"]) + ident.varint(inp["hash_type"]) + inp["digest"])
                    self.assertEqual(cbor.encode(pid), v["canonical"])
                elif cat == "signature":
                    self._signature(v)
                elif kind == "encode_equal":
                    self.assertEqual(cbor.encode(v["input"]).hex(), v["canonical"].hex())
                    # Appendix E's re-encode precondition: canonical bytes -> decode -> encode is byte-identical.
                    back, f = cbor.decode(v["canonical"])
                    self.assertEqual(f.non_canonical, [], f"canonical bytes read as non-canonical: {f.non_canonical}")
                    self.assertTrue(_same(back, v["input"]), f"decoded {back!r} != input {v['input']!r}")
                    self.assertEqual(cbor.encode(back), v["canonical"])
                else:
                    self.fail(f"unknown vector kind {kind!r} — neither run nor declared")

    def _reject(self, v):
        """§6.3: a tag anywhere is a rejection. The decoder must find it — and not by tripping on trailing bytes."""
        try:
            _, f = cbor.decode(v["canonical"])
        except cbor.CBORError as e:
            self.fail(f"decoder raised instead of finding the tag: {e}")
        self.assertTrue(f.tags, "decode_reject vector decoded with no tag found")

    def _signature(self, v):
        seed, ent = v["input"]["seed"], v["input"]["entity"]
        e = ident.entity(ent["type"], ent["data"])
        reproduces = [m for m in ident.SIGN_MESSAGES if ed25519.sign(seed, ident.signing_message(e, m)) == v["canonical"]]
        SIGNATURE_MESSAGE_FOUND[v["id"]] = reproduces
        print(f"\n{v['id']}: reproduces signing {reproduces or 'NONE of ' + str(ident.SIGN_MESSAGES)} (F30; §7.3 says hash33)", file=sys.stderr)
        self.assertEqual(len(reproduces), 1, "the vector should reproduce under exactly one candidate message")


class Codec(unittest.TestCase):
    """Negative controls for the decoder's refusals and findings, so a green corpus run is not a lenient decoder."""

    def test_refusals(self):
        for name, data in [
            ("duplicate key", bytes.fromhex("a2616101616102")),
            ("int/true key collapse", bytes.fromhex("a201f5f5f5")),  # {1: true, true: true}
            ("invalid utf-8", bytes.fromhex("62c328")),
            ("trailing bytes", bytes.fromhex("a0a0")),
            ("truncated", bytes.fromhex("a1616101"[:-2])),
        ]:
            with self.subTest(name):
                with self.assertRaises(cbor.CBORError):
                    cbor.decode(data)

    def test_findings(self):
        for name, data, pat in [
            ("non-minimal int", bytes.fromhex("1801"), "non-minimal"),
            ("unsorted keys", bytes.fromhex("a2626262016161" + "02"), "order"),
            ("indefinite array", bytes.fromhex("9f01ff"), "indefinite"),
            ("non-shortest float", bytes.fromhex("fb3ff0000000000000"), "shortest"),
        ]:
            with self.subTest(name):
                _, f = cbor.decode(data)
                self.assertTrue(any(re.search(pat, x) for x in f.non_canonical), f.non_canonical)


if __name__ == "__main__":
    unittest.main()
