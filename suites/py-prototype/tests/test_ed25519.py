"""Ed25519 against RFC 8032 §7.1, whose vectors are extracted verbatim into rfc8032-7.1.json (source + sha256 inside)."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prototype import ed25519  # noqa: E402

VECTORS = json.loads((Path(__file__).parent / "rfc8032-7.1.json").read_text())["vectors"]


class RFC8032(unittest.TestCase):
    def test_vectors(self):
        self.assertEqual(len(VECTORS), 5, "RFC 8032 §7.1 has five Ed25519 vectors")
        for v in VECTORS:
            with self.subTest(test=v["test"]):
                sk, pk = bytes.fromhex(v["secret_key"]), bytes.fromhex(v["public_key"])
                msg, sig = bytes.fromhex(v["message"]), bytes.fromhex(v["signature"])
                self.assertEqual(ed25519.public_key(sk), pk)
                self.assertEqual(ed25519.sign(sk, msg), sig)
                self.assertTrue(ed25519.verify(pk, msg, sig))

    def test_verify_refuses(self):
        """Controls: verify must be able to say no, or the positive cases above measure nothing."""
        v = VECTORS[1]
        sk, pk, msg, sig = (bytes.fromhex(v[k]) for k in ("secret_key", "public_key", "message", "signature"))
        self.assertFalse(ed25519.verify(pk, msg + b"\x00", sig), "altered message")
        bad = bytearray(sig)
        bad[0] ^= 1
        self.assertFalse(ed25519.verify(pk, msg, bytes(bad)), "altered R")
        s = int.from_bytes(sig[32:], "little") + ed25519.L  # same point equation, S out of range
        self.assertFalse(ed25519.verify(pk, msg, sig[:32] + s.to_bytes(32, "little")), "S >= L (RFC 8032 §5.1.7)")
        self.assertFalse(ed25519.verify(bytes.fromhex(VECTORS[0]["public_key"]), msg, sig), "wrong key")


if __name__ == "__main__":
    unittest.main()
