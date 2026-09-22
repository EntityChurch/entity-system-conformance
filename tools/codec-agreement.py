#!/usr/bin/env python3
"""The two canonical-CBOR codecs in this repo must agree, byte for byte.

⛔⭐ WHY THIS EXISTS. This repo contains TWO independent canonical-CBOR encoders:

    tools/cbordiag.py                       the requirement corpus (requirement_corpus_digest)
    suites/py-prototype/prototype/cbor.py   the instrument, on the wire, against real peers

**Nothing compared them until 2026-09-17**, and on that day they DISAGREED on the corpus's own
map-key ordering rule. `cbordiag` sorted keys bytewise (RFC 8949 §4.2.1) and its module header said
so in as many words; the suite codec sorted length-first (§4.2.3, `ENTITY-CORE-PROTOCOL` §1.3) and
parameterized both. Arch ruled length-first in `F22`/`CQ-15`
(`ROUTING-2026-09-16-g-entity-system-conformance-the-encoding-batch-is-ruled-…` §3).

⭐ **THE POINT IS NOT THE BUG. IT IS THAT WE HAD THE SECOND IMPLEMENTATION ALREADY.** The whole
argument of this seat is that two independent implementations of the same rule catch each other's
errors -- and we were running two, in one tree, for the repo's entire life, with no instrument
comparing them. **The disagreement was found by reading a counterpart's routing packet.** Every
gate here was green.

⚠ WHAT THIS DOES NOT DO:
  - It does not decide WHICH codec is right. It reports that they differ and shows both encodings.
    Which one conforms is a specification question; `cbordiag --self-test` pins §4.2.3 directly.
  - It does not prove the two codecs are independent -- they are not, in the sense that one author
    wrote both. It proves they AGREE, which is the weaker and checkable claim.
  - It covers the structures below, not the whole CBOR space. Each case is here because it can
    discriminate something; `_ORDERING` is the one that actually fired.

Usage:  python3 tools/codec-agreement.py [--self-test]
Exit:   0 agree · 1 disagree · 2 could not look
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "suites" / "py-prototype"))

# ⛔ A MISSING CODEC IS "COULD NOT LOOK", NEVER A PASS. A gate whose subject has moved and which
# reports success is the fail-open shape this repo refuses everywhere (item-gate's MIN_ITEMS, F57).
try:
    import cbordiag
    from prototype import cbor as suitecbor
except Exception as e:  # noqa: BLE001
    print(f"codec-agreement: COULD NOT LOOK — a codec did not import: {e}", file=sys.stderr)
    raise SystemExit(2)

# ⭐ THE DISCRIMINATING CASE, first, because it is the one that fired. bstr h'0000000000' encodes to
# 6 bytes with head 0x45; tstr "a" encodes to 2 bytes with head 0x61. Length order and head-byte
# order DISAGREE, which is the only way to tell §4.2.3 from §4.2.1 -- arch's minimal witness.
# ⚠ Pure-text keys CANNOT discriminate and a suite of them proves nothing here: a tstr of length
# n < 24 has head byte 0x60+n, monotonic in the length, so bytewise already sorts by length.
_ORDERING = {b"\x00\x00\x00\x00\x00": 1, "a": 2}

CASES = [
    ("map ordering, discriminating (§4.2.3 vs §4.2.1)", _ORDERING),
    ("map ordering, text keys (CANNOT discriminate — kept to show it cannot)", {"aa": 1, "b": 2}),
    ("text keys across the 23/24 head boundary", {"x" * 23: 1, "y" * 24: 2}),
    ("nested maps", {"outer": {"inner": 1, "b": [1, 2]}}),
    ("integers at head boundaries", [0, 23, 24, 255, 256, 65535, 65536, -1, -24, -25]),
    ("byte strings", {"b": b"", "c": b"\x00\xff"}),
    ("booleans and null", [True, False, None]),
    ("empty containers", [{}, [], {"e": {}}]),
    ("unicode text", {"k": "café ü 中"}),
]


def compare():
    findings = []
    for name, value in CASES:
        try:
            a = cbordiag.encode(value)
        except Exception as e:  # noqa: BLE001
            findings.append((name, f"cbordiag raised: {e}", ""))
            continue
        try:
            b = suitecbor.encode(value)
        except Exception as e:  # noqa: BLE001
            findings.append((name, "", f"suite codec raised: {e}"))
            continue
        if a != b:
            findings.append((name, a.hex(), b.hex()))
    return findings


def self_test():
    """The gate must be able to FAIL. A check that cannot be made to fail has not been shown to
    measure anything -- and this one's whole value is catching a disagreement, so a green run with
    a broken comparison is indistinguishable from agreement."""
    real = cbordiag.encode
    try:
        cbordiag.encode = lambda v: real(v) + b"\x00"  # a codec that disagrees on everything
        if not compare():
            print("codec-agreement SELF-TEST FAILED: a deliberately disagreeing codec was not "
                  "detected — the comparison is not comparing.", file=sys.stderr)
            return 1
    finally:
        cbordiag.encode = real
    if compare():
        print("codec-agreement SELF-TEST FAILED: the two codecs disagree with no defect planted.",
              file=sys.stderr)
        return 1
    print(f"codec-agreement self-test: OK — {len(CASES)} case(s); a planted disagreement is caught "
          "and the unmodified pair agrees")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    findings = compare()
    for name, a, b in findings:
        print(f"  DISAGREE  {name}\n      tools/cbordiag.py        {a}\n"
              f"      suites/py-prototype      {b}", file=sys.stderr)
    if findings:
        print(f"codec-agreement: {len(findings)} of {len(CASES)} case(s) DISAGREE. ⛔ The two codecs "
              "encode the same value differently; one of them is wrong about the specification and "
              "`cbordiag --self-test` pins the rule.", file=sys.stderr)
        return 1
    print(f"codec-agreement: {len(CASES)} case(s) — both codecs byte-identical "
          "(including the §4.2.3/§4.2.1 discriminating map, which is the one that once differed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
