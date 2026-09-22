"""`S-1` — the second-codec cross-bless of the recomputed `signature` vectors.

⭐ WHY THIS FILE EXISTS, AND WHY IT IS NOT IN test_corpus.py. Two seats independently named this
cross-bless as owed BY US and blocking:

  arch  `ROUTING-2026-09-16-d-entity-system-conformance-cq-22-is-ruled-…` §5:
        "The cross-bless is yours, and it is named rather than assumed. s1-py is the natural second
         codec … One oracle cannot measure itself, and this defect's own discovery met the two-codec
         standard — it would be a poor outcome to fix it with one."
  go    `ROUTING-2026-09-16-b-S1-signature-vectors-recomputed-under-CQ-22-and-a-standing-verifier`:
        "The values are verified two independent ways; the second codec cross-bless (s1-py) is
         still owed by the conformance seat BEFORE THE DIGEST PUBLISHES."

⛔ THE INPUTS HERE ARE THE ENTITIES, NEVER GO'S BYTES. We derive each signature from `(seed, type,
data)` with this suite's own canonical-CBOR encoder, its own SHA-256 framing and its Ed25519 written
from RFC 8032, and only then compare to the value go published. **If go's value were used anywhere
as an input, this would be a transcription check and would measure nothing** — which is exactly the
failure the original defect was: an artifact carrying a construction nobody re-derived.

⭐ AND IT MEASURES WHICH MESSAGE REPRODUCES RATHER THAN ASSERTING §7.3's. `hash33` must be the ONLY
candidate of the three that reproduces. A vector that reproduced under two would mean the candidates
are not distinguishing, and asserting §7.3 directly would hide that. This is the same posture that
found `F30` in the first place: the corpus was READ for its whole life and the defect appeared the
moment somebody EXECUTED it.

RETIREMENT: when `entity-core-protocol` lands the new `conformance-vectors.cbor` and a snapshot is
pinned here, `test_corpus.py`'s `_signature` covers these vectors from the artifact itself and this
file becomes redundant. **Delete it then — do not leave it as a second home for the same fact.**
Until then the new vectors exist only inside a routing packet, and this is the only thing that has
checked them.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prototype import ed25519, ident  # noqa: E402

# entity-core-go `ROUTING-2026-09-16-b-S1-signature-vectors-recomputed-under-CQ-22-and-a-standing-verifier` §1.
# Cited by FULL STEM because <date>-<letter> is unique to one repo on one day, which is not unique.
GO_VECTORS = {
    "signature.1": (bytes(32), "test/v1", {"x": 1},
                    "25217cd5348f32bd96c35886034f0b8bac111a5632b706acaed325f7cd93b27b"
                    "2dfe95023a8308f36cd282f81666ee64c5382af2b02dd7b5702c5cf4d759b509"),
    "signature.2": (b"\xff" * 32, "test/v1", {"z": 1, "a": 2},
                    "947a1e85f15f35f9461e575d2cd06b5b8132c74e955c4dd112a49841dc11dda1"
                    "b98d48545bbb972dcf003cb139e298b1dbd7377809e54ce38b04ebb7bbea1d07"),
    "signature.3": (bytes(range(32)), "test/v1", {"outer": {"inner": 1}},
                    "dd92d8c32722a4e245c1f44a3667a20a6dcc3e58614f9d4704db765d55635974"
                    "52b3d94bfb2dcfe54b6fe597a8e95657ab369b3582d401488476faf279a7ac07"),
    # NEW at this recompute. Appendix E's cross-check vector: its signed message is content_hash.1's
    # canonical, so the sign construction is checkable against the hash category BY INSPECTION.
    # ⭐ Arch called this "the only delta of the five that is not a correction, and the one that
    # stops this recurring" -- nothing had related the two categories, which is why the defect hid.
    "signature.4": (bytes(32), "system/empty", {},
                    "5ef76864cd750b810b75e0d6f7ea15fe5d9bca34e99fa92d0898b3d5fed0c3a0"
                    "295e9b9d105239e423ba2e87b564512040558b25703fdb436de7f2fded65140a"),
}

# `content_hash.1`'s `canonical` in the CURRENT committed corpus (sha256 9695b1f1…c6dc), which is
# unchanged by this recompute. The whole point of signature.4 is that these must be byte-identical.
CONTENT_HASH_1 = "005f3139e342f5ef35c1e0eb3140c4511c469d604979d20542bc2ab92fd0ca396b"


class CrossBlessS1(unittest.TestCase):
    def test_each_vector_reproduces_under_exactly_hash33(self):
        for vid, (seed, typ, data, expected) in GO_VECTORS.items():
            with self.subTest(vid):
                ent = ident.entity(typ, data)
                hits = [m for m in ident.SIGN_MESSAGES
                        if ed25519.sign(seed, ident.signing_message(ent, m)).hex() == expected]
                self.assertEqual(
                    hits, ["hash33"],
                    f"{vid}: reproduces under {hits or 'NO candidate message'}; §7.3 [MUST] is the "
                    f"full content_hash (format code + digest). Candidates: {ident.SIGN_MESSAGES}")

    def test_signature_4_signs_content_hash_1(self):
        """Appendix E's cross-check, verified rather than trusted.

        ⚠ This is the assertion that makes the corpus self-checking. Without it the `signature`
        category and the `content_hash` category remain unrelated, which is the condition under
        which the original construction defect survived for the artifact's entire life.
        """
        msg = ident.signing_message(ident.entity("system/empty", {}), "hash33")
        self.assertEqual(msg.hex(), CONTENT_HASH_1)

    def test_a_wrong_message_does_not_reproduce(self):
        """The negative control. A check that cannot be made to fail has not been shown to measure
        anything -- and the two rejected candidates here are the two readings the corpus and
        `ENTITY-NATIVE-TYPE-SYSTEM` §10.2 actually carried, not invented wrong answers."""
        seed, typ, data, expected = GO_VECTORS["signature.1"]
        ent = ident.entity(typ, data)
        for wrong in ("digest32", "ecf"):
            with self.subTest(wrong):
                self.assertNotEqual(
                    ed25519.sign(seed, ident.signing_message(ent, wrong)).hex(), expected,
                    f"{wrong} reproduced go's value -- the candidates are not distinguishing and "
                    f"the positive result above proves nothing")


if __name__ == "__main__":
    unittest.main()
