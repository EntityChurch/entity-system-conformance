"""IMPLEMENTS equals the CHECKS table, and ECP-R6's suite-side negative control can fail."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from s1py import checks, wire  # noqa: E402

HERE = Path(__file__).resolve().parent.parent


class Manifest(unittest.TestCase):
    def test_implements_equals_checks(self):
        ids = [l.strip() for l in (HERE / "IMPLEMENTS").read_text().splitlines() if l.strip() and not l.startswith("#")]
        self.assertEqual(sorted(ids), sorted(checks.CHECKS))
        reqs = HERE.parent.parent / "requirements" / "core"
        for rid in ids:
            self.assertTrue((reqs / f"{rid}.toml").is_file(), rid)


def _resp(rid, status, code=None, listing_path=None):
    result = {"type": "system/protocol/error", "data": {"code": code}}
    if listing_path is not None:
        result = {"type": "system/tree/listing", "data": {"path": listing_path, "entries": {}, "count": 0, "offset": 0}}
    env = {"root": {"type": wire.RESPONSE, "data": {"request_id": rid, "status": status, "result": result}}}
    return wire.Outcome("response", status=status, code=code, request_id=rid, envelope=env)


class R6Matcher(unittest.TestCase):
    REQ = {"a": "listing-type", "b": "unregistered", "c": "listing-handler"}

    def test_correct_echo_holds(self):
        rs = [_resp("c", 200, listing_path="system/handler/"), _resp("a", 200, listing_path="/2Kx/system/type/"),
              _resp("b", 404, "handler_not_found")]
        self.assertEqual(checks.match_by_content(self.REQ, rs)[0], True)

    def test_rotated_ids_refused(self):
        rs = [_resp("b", 200, listing_path="system/type/"), _resp("c", 404, "handler_not_found"),
              _resp("a", 200, listing_path="system/handler/")]
        self.assertEqual(checks.match_by_content(self.REQ, rs)[0], False)

    def test_indistinguishable_is_could_not_look(self):
        rs = [_resp("a", 403, "capability_denied"), _resp("b", 404, "handler_not_found"), _resp("c", 403, "capability_denied")]
        self.assertIsNone(checks.match_by_content(self.REQ, rs)[0])


if __name__ == "__main__":
    unittest.main()
