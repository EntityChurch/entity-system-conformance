"""IMPLEMENTS equals the CHECKS table, and ECP-R6's suite-side negative control can fail."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from s1py import checks, emitted, wire  # noqa: E402

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


class CodedRefusal(unittest.TestCase):
    """The §4.5 hello arms assert status AND decoded code; each shape that is not both must be refused."""

    def test_exact_pair_holds(self):
        self.assertIs(checks._coded_refusal("r", _resp("h", 400, "incompatible_protocol"), 400, "incompatible_protocol").held, True)

    def test_near_misses_refused(self):
        for o in (_resp("h", 400, "invalid_request"), _resp("h", 409, "incompatible_protocol"), _resp("h", 400, None),
                  wire.Outcome("close", detail="EOF"), wire.Outcome("timeout")):
            self.assertIs(checks._coded_refusal("r", o, 400, "incompatible_protocol").held, False, o.brief())

    def test_control_refuses_the_probed_code(self):
        self.assertIs(checks._not_code_control(_resp("h", 400, "invalid_request"), "invalid_request", "x").held, False)
        self.assertIsNone(checks._not_code_control(wire.Outcome("close"), "invalid_request", "x").held)


class EmittedFixtures(unittest.TestCase):
    """The suite-authored fixture every emitted-side control breaks must itself satisfy every emitted-side predicate —
    otherwise a control 'refusing' a broken copy proves nothing about the break."""

    def test_unbroken_fixture_passes_every_predicate(self):
        env = checks._fixture_env()
        for pred in (emitted.all_hashes_recompute, emitted.all_hashes_flat, emitted.included_keys_match,
                     emitted.typed_fields, emitted.optional_nulls):
            self.assertIs(pred([env])[0], True, pred.__name__)
        from s1py import cbor
        self.assertTrue(emitted.frame_is_canonical(cbor.encode(env))[0])

    def test_tag_is_not_unwrapped(self):
        from s1py import cbor
        ch = checks._fixture_env()["root"]["content_hash"]
        self.assertIs(emitted.hash_shape(cbor.Tag(37, ch))[0], False)

    def test_empty_input_is_vacuous_not_pass(self):
        for pred in (emitted.all_hashes_recompute, emitted.all_hashes_flat, emitted.included_keys_match,
                     emitted.typed_fields, emitted.optional_nulls):
            self.assertIsNone(pred([{"root": None, "included": {}}])[0], pred.__name__)


class NoPeer(unittest.TestCase):
    """F57's negative control, executed: every check against an address where nothing listens. A connection that never
    opened is not an observation of any peer, so the only permitted verdict is SKIP. Before the fix this run scored four
    FAILs, three INCONCLUSIVEs and a PASS."""

    def test_every_check_is_could_not_look(self):
        ctx = checks.Ctx("127.0.0.1:1", 2.0, "hash33", False, 0.5)
        scored = {}
        for rid in checks.CHECKS:
            r = checks.run(rid, ctx)
            self.assertNotEqual(r.suite_check, "suite-error", f"{rid}: {r.message}")
            if r.verdict != "SKIP":
                scored[rid] = f"{r.verdict}: {r.message[:120]}"
        self.assertEqual(scored, {})


if __name__ == "__main__":
    unittest.main()
