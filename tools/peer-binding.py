#!/usr/bin/env python3
"""peer-binding — the peer set as DATA, and every peer recorded by IDENTITY rather than by name.

    tools/peer-binding.py --resolve --suite py-prototype --keystone <tree>   # the set, expanded
    tools/peer-binding.py --identity PEER --keystone <tree>                  # one peer's identity record
    tools/peer-binding.py --lint                                             # lint-peer-diversity
    tools/peer-binding.py --self-test

`ADR-0003` §7, built 2026-09-16. **⛔ `peer: "zig"` is not a measurement. `peer: zig @ <commit>,
host sha256 <…>, contract absent` is.**

WHY. Until today the peer set lived in `KEYSTONE_PEERS ?= python rust go typescript` and was
overridden on the command line for the 33- and 37-peer runs, so the input that decided every
published number of ours was an argument someone typed and no artifact recorded. That is
`AGENTS.md`'s fairness rule — *the peer pair is a parameter* — one level up, on the suite/peer axis.

⛔ **THE RULE THAT SHAPES THIS WHOLE FILE: WE CONSUME, WE NEVER RE-MEASURE, AND WE NEVER COPY.**
Adopted from `entity-system-generator`'s `tools/check-eligible.py` rather than invented
(`ADR-0003` §7.2), in their words: *"Keystone certifies each peer and publishes
`KEYSTONE-PEER-REPORT.json`; we never re-measure what that report certifies … a copy of that
vocabulary here is exactly the kind of fact `AGENTS.md` says we never keep. **A declared name
keystone does not define FAILS.**"*

  * Every peer NAME we declare is checked against keystone's roster on every run. An unknown name is
    a finding, never a skip — a set that silently drops a misspelled peer measures a smaller cohort
    and reports it as the whole one.
  * Every peer FACT — language, tier, spec pin, certification, delivery commit — is read out of
    keystone's tree at the moment of use. **Nothing about a peer is stored here or in `PEERS.diag`.**

⚠ **`contract_certified: absent` IS THE HONEST VALUE FOR 43 OF 46, AND IT IS EMITTED, NOT OMITTED.**
Three peers carry a `KEYSTONE-PEER-REPORT.json`. For the rest we drive an uncertified convention,
and a verdict that simply leaves the field out is indistinguishable from one taken before the field
existed. We also consume only part A (`run`) of a five-part certification and say so, because
reporting *"certified"* when five parts were certified and one bore on you is an overclaim
(`ADR-0003` §7.2).

⛔ **`spec_pin` DOES NOT EXIST YET AND THIS TOOL REPORTS THAT RATHER THAN GUESSING.** Keystone asked
us to name the field; we answered on 2026-09-16 (`ROUTING-2026-09-16-a-…`, a `spec_pin` column in
`tools/peer-tiers.tsv`). Until they fill it, every peer's pin resolves to `unknown` with the reason
attached. ⚠ **It must NOT fall back to `profile.toml`'s `[spec] v7_version_pinned`**, which looks
exactly like the field we want and is present on 24 of 46, spans five v7-era values, and mentions
`0.8.2` on **zero** peers while the cohort sits at `0.8.2.25`. A stale field parses and answers with
confidence; that is why it is worse than an absent one, and why this tool refuses to read it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # __pycache__ is .gitignore'd; lint-ignored refuses it (AP-8)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cbordiag  # noqa: E402  — tools' OWN codec; never the suite's (lint-suite-independence)

ROOT = Path(__file__).resolve().parent.parent
SUITES = ROOT / "suites"

# The roster file in KEYSTONE's tree. A path, not a vocabulary — the names inside it are theirs.
ROSTER = "tools/peer-tiers.tsv"
PEER_REPORT = "status/KEYSTONE-PEER-REPORT.json"
PEER_DIR = "protocol-generator"

# ⛔ The column we asked keystone for (ROUTING-2026-09-16-a). Absent today, by design not by defect.
SPEC_PIN_COLUMN = "spec_pin"
SPEC_PIN_ABSENT = ("unknown — no `spec_pin` column in keystone's roster. Asked 2026-09-16 "
                   "(ROUTING-2026-09-16-a-entity-core-keystone-…); until it lands, the spec revision "
                   "a peer was swept to is NOT machine-readable anywhere in their tree. "
                   "⛔ profile.toml's [spec] v7_version_pinned is NOT a fallback: 24 of 46, five "
                   "v7-era values, 0 of 46 mentioning 0.8.2.")

# A floor, because this file's fragile parts are a glob and a TSV parse, and both fail OPEN — a
# roster that stops parsing yields an empty set, and an empty set validates perfectly.
MIN_ROSTER = 20


class GateError(Exception):
    """Could-not-look. Exits 2, never 1 — an unreadable input is not a clean result."""


def load_diag(path: Path) -> dict:
    if not path.is_file():
        raise GateError(f"no file at {path}")
    try:
        return cbordiag.parse(path.read_text())
    except Exception as exc:                                  # noqa: BLE001
        raise GateError(f"{path}: {exc}") from exc


def read_roster(keystone: Path) -> dict[str, dict]:
    """Keystone's roster, parsed as data. Their columns, their names, read every run."""
    path = keystone / ROSTER
    if not path.is_file():
        raise GateError(f"no roster at {path}")
    rows, header = {}, None
    for line in path.read_text().splitlines():
        line = line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.split("\t")
        if header is None:
            header = [c.strip() for c in cells]
            continue
        row = dict(zip(header, [c.strip() for c in cells]))
        name = row.get("peer")
        if name:
            rows[name] = row
    if header is None:
        raise GateError(f"{path}: no header row — the roster did not parse")
    if len(rows) < MIN_ROSTER:
        raise GateError(f"{path}: {len(rows)} peer(s), below MIN_ROSTER={MIN_ROSTER}. A roster that "
                        f"has stopped parsing yields an empty cohort, and an empty cohort validates.")
    return rows


def spec_pin(row: dict) -> dict:
    """The pin keystone has not published yet. ⛔ Never inferred, never defaulted to a v7 value."""
    value = (row.get(SPEC_PIN_COLUMN) or "").strip()
    if not value:
        return {"value": "unknown", "why": SPEC_PIN_ABSENT}
    if value == "unknown":
        # Their explicit token, which we asked for precisely so this case is distinguishable.
        return {"value": "unknown", "why": "keystone declares the pin unknown for this peer"}
    return {"value": value, "source": f"entity-core-keystone {ROSTER} ({SPEC_PIN_COLUMN}), read at use"}


def identity(keystone: Path, peer: str, roster: dict[str, dict]) -> dict:
    """One peer's IDENTITY. Consumed from keystone's tree; nothing here is measured or stored by us."""
    if peer not in roster:
        raise GateError(f"peer {peer!r} is not on keystone's roster ({ROSTER}). A declared name "
                        f"keystone does not define FAILS — it is not silently dropped.")
    row = roster[peer]
    rec: dict = {
        "peer": peer,
        "roster": {k: v for k, v in row.items() if k != "peer"},
        "spec_pin": spec_pin(row),
        "contract_certified": "absent",
        "contract_parts_consumed": ["run"],
        "contract_note": ("only part A (`run`) of the peer contract bears on us. A consumer that "
                          "reads a five-part certification and needs one part must not report "
                          "'certified' as though all five bore on it (ADR-0003 §7.2)."),
    }
    report = keystone / PEER_DIR / peer / PEER_REPORT
    if not report.is_file():
        rec["delivery"] = {"commit": None, "tree_dirty": None,
                           "why": f"no {PEER_REPORT} for this peer — uncertified convention, 43 of 46"}
        return rec
    try:
        data = json.loads(report.read_text())
    except Exception as exc:                                  # noqa: BLE001
        raise GateError(f"{report}: {exc}") from exc
    delivery = data.get("delivery") or {}
    rec["contract_certified"] = data.get("verdict") or "false"
    rec["contract_version"] = data.get("contract_version")
    rec["contract_digest"] = data.get("contract_digest")
    rec["delivery"] = {
        "commit": delivery.get("commit"),
        "tree_dirty": delivery.get("tree_dirty"),
        "artifacts": {k: v.get("sha256") for k, v in (delivery.get("artifacts") or {}).items()},
        "toolchain_image": (delivery.get("toolchain_image") or {}).get("id"),
    }
    core = data.get("core_conformance") or {}
    rec["core_conformance"] = {k: core.get(k) for k in
                               ("executed_check_set_digest", "pinned_check_set_digest", "ok")}
    return rec


def declared_sets(suite: str) -> dict:
    return load_diag(SUITES / suite / "PEERS.diag")


def resolve(suite: str, keystone: Path) -> dict:
    """Expand the declared set against the live roster. Membership is a RULE; this applies it."""
    spec = declared_sets(suite)
    roster = read_roster(keystone)
    excluded: dict[str, str] = {}
    for block in spec.get("exclusions") or []:
        for p in block.get("peers") or []:
            excluded[p] = block.get("reason", "excluded")
    out: dict = {"suite": spec.get("suite", suite), "sources": {}, "findings": [],
                 "excluded": excluded, "roster_size": len(roster)}
    for src in spec.get("sources") or []:
        name = src.get("source")
        if src.get("include") == "roster":
            peers = [p for p in sorted(roster) if p not in excluded]
        else:
            peers = list(src.get("peers") or [])
            # ⛔ Only keystone peers are on keystone's roster. The generator's and core-go's are not,
            # and checking them against it would be a category error that fails every run.
            if name == "keystone":
                for p in peers:
                    if p not in roster:
                        out["findings"].append(
                            f"{suite}: declared keystone peer {p!r} is not on the roster ({ROSTER})")
        out["sources"][name] = peers
    # An exclusion naming a peer that is not on the roster is a stale exclusion, and a stale
    # exclusion silently shrinks nothing — which is why it has to be said out loud.
    for p in excluded:
        if p not in roster:
            out["findings"].append(
                f"{suite}: exclusion names {p!r}, which is not on keystone's roster — stale exclusion")
    return out


def lint() -> int:
    """`lint-peer-diversity` — ADR-0003 §7.3 clause 3. ⚠ VACUOUS TODAY AND IT SAYS SO EVERY RUN."""
    suites = sorted(p.name for p in SUITES.iterdir() if (p / "PEERS.diag").is_file()) \
        if SUITES.is_dir() else []
    if not suites:
        print("lint-peer-diversity: COULD NOT LOOK — no suite declares suites/*/PEERS.diag",
              file=sys.stderr)
        return 2

    findings: list[str] = []
    sets: dict[str, dict[str, set]] = {}
    for suite in suites:
        try:
            spec = declared_sets(suite)
        except GateError as exc:
            print(f"lint-peer-diversity: COULD NOT LOOK — {exc}", file=sys.stderr)
            return 2
        if not spec.get("rationale"):
            findings.append(f"{suite}: PEERS.diag declares no rationale. ADR-0003 §7.3 clause 1 "
                            f"requires a peer set declared WITH a rationale — a set with no argument "
                            f"behind it is the Makefile variable again, in a new file.")
        by_source: dict[str, set] = {}
        for src in spec.get("sources") or []:
            key = src.get("source") or "?"
            by_source[key] = ({"<roster>"} if src.get("include") == "roster"
                              else set(src.get("peers") or []))
        sets[suite] = by_source

    exempt: set = set()
    # Clause 1: two suites whose declared sets are identical or nested.
    #
    # ⛔⭐ THE SINGLE-MEMBER EXEMPTION, added 2026-09-17 the first time this gate ever fired, and
    # declared out loud on every run rather than applied silently. A source with ONE member (today:
    # `core-go`, whose only peer is the reference `entity-peer`) makes "identical" FORCED BY
    # ARITHMETIC: any two suites that test it at all declare the same set, and the only way to go
    # green is for one suite to STOP TESTING THE REFERENCE IMPLEMENTATION -- the peer a second
    # opinion is most valuable about. A rule whose only satisfying move damages the thing it
    # protects is mis-scoped, not violated.
    #
    # ⭐ It is arch's §6a shape, in our own gate, found the same day we read it: *"1 of 26 measured
    # compliance against an obligation that does not arise for the other 25 -- a denominator of
    # documents where the rule's denominator is operations."* Here the rule's denominator is
    # PARTITIONABLE PEERS, and for a one-peer source there is no partition to choose. The
    # obligation does not arise.
    #
    # ⚠ THIS IS A SCOPE CORRECTION, NOT A SHRINK. Neither suite gave up a peer to make the gate
    # pass -- `rs-conformance` kept core-go and filed the question (`RSC-PEERS-3`) instead of
    # dropping it, which is the behaviour ADR-0003 asks for. ⛔ ADR-0003 §7.3 clause 3 still says
    # what it said; amending it is owed and is NOT done here.
    for source, members in sorted({s: v for m in sets.values() for s, v in m.items()}.items()):
        if "<roster>" not in members and len(members) == 1:
            exempt.add(source)
            print(f"  EXEMPT source {source!r} has ONE member ({next(iter(members))}): identical "
                  f"sets are forced by arithmetic, not chosen, so clause 3 does not arise. "
                  f"ADR-0003 §7.3 clause 3 needs amending to say so (owed, not done).")

    pairs = [(a, b) for i, a in enumerate(suites) for b in suites[i + 1:]]
    for a, b in pairs:
        for source in set(sets[a]) & set(sets[b]):
            if source in exempt:
                continue
            sa, sb = sets[a][source], sets[b][source]
            if "<roster>" in sa and "<roster>" in sb:
                rel = "identical (both declare the roster)"
            elif sa == sb:
                rel = "identical"
            elif sa <= sb or sb <= sa:
                rel = "nested"
            else:
                continue
            findings.append(
                f"{a} and {b} declare {rel} peer sets for source {source!r}. ADR-0003 §7.3 clause 3: "
                f"that is one instrument wearing two names, and it is the cohort-consistency failure "
                f"AGENTS.md warns about (AP-10). ⚠ If one of them declares the ROSTER, read that "
                f"suite's PEERS.diag `suite_2_note` FIRST — nesting may be forced by arithmetic "
                f"rather than chosen, and the ADR does not settle that case.")

    for f in findings:
        print(f"  FINDING {f}", file=sys.stderr)

    print(f"lint-peer-diversity: {len(suites)} suite(s) declaring a peer set — {len(findings)} finding(s)")
    if len(suites) < 2:
        # ⭐ ADR-0003 §7.3 clause 4, kept verbatim as behaviour: a gate that cannot fail yet is
        # honest only if it reports that it cannot. This line is the whole reason to build it early.
        print("  ⚠ CLAUSE 1 IS VACUOUS: one suite exists, so 'two suites' peer sets' has no instance "
              "and this gate CANNOT FAIL on it today. It is built before suite 2 so that it fires "
              "the moment suite 2 declares an overlapping set, instead of being written afterwards "
              "by someone who has already chosen.")
        print("  ⚠ CLAUSE 2 (no requirement's evidence resting on one peer or one language) needs "
              "collected run data and is NOT implemented. Named, not silently skipped.")
    return 1 if findings else 0


def self_test() -> int:
    """Executed control. Every rule this file enforces is planted and required to refuse."""
    import copy
    import tempfile

    roster_text = ("# comment\npeer\ttier\tlast_measured_pin\tnote\n"
                   + "".join(f"p{i}\tM3\tabc1234\tn\n" for i in range(MIN_ROSTER + 5)))

    with tempfile.TemporaryDirectory() as td:
        ks = Path(td) / "keystone"
        (ks / "tools").mkdir(parents=True)
        (ks / ROSTER).write_text(roster_text)
        roster = read_roster(ks)
        if len(roster) != MIN_ROSTER + 5:
            print(f"SELF-TEST FAILED: roster parsed {len(roster)} rows", file=sys.stderr)
            return 1

        planted = []

        # 1. ⛔ THE FLOOR. A roster that stops parsing must be COULD-NOT-LOOK, never an empty cohort.
        (ks / "tools" / "short.tsv").write_text("peer\ttier\np0\tM3\n")
        try:
            read_roster_short = ks / "tools" / "short.tsv"
            saved, globals()["ROSTER"] = ROSTER, "tools/short.tsv"
            try:
                read_roster(ks)
                planted.append(("a 1-peer roster was ACCEPTED", False))
            except GateError:
                planted.append(("1-peer roster refused (floor)", True))
            finally:
                globals()["ROSTER"] = saved
            assert read_roster_short.is_file()
        except AssertionError:
            return 1

        # 2. ⛔ THE RULE THAT MATTERS MOST HERE: a declared name keystone does not define FAILS.
        try:
            identity(ks, "not-a-peer", roster)
            planted.append(("an off-roster peer name was ACCEPTED", False))
        except GateError:
            planted.append(("off-roster peer name refused", True))

        # 3. spec_pin must NOT invent a value when the column is absent.
        pin = spec_pin(roster["p0"])
        planted.append(("absent spec_pin resolves to `unknown` with a reason",
                        pin["value"] == "unknown" and "profile.toml" in pin["why"]))

        # 4. ...and must pass a real value through when keystone fills the column.
        pin2 = spec_pin({"peer": "p0", SPEC_PIN_COLUMN: "0.8.2.25"})
        planted.append(("a filled spec_pin is passed through, not re-derived",
                        pin2["value"] == "0.8.2.25"))

        # 5. ⛔ An explicit `unknown` from keystone is DISTINGUISHABLE from an absent column.
        pin3 = spec_pin({"peer": "p0", SPEC_PIN_COLUMN: "unknown"})
        planted.append(("keystone's explicit `unknown` is distinguished from an absent column",
                        pin3["value"] == "unknown" and "profile.toml" not in pin3["why"]))

        # 6. An uncertified peer reports `absent`, and EMITS the field rather than omitting it.
        rec = identity(ks, "p0", roster)
        planted.append(("an uncertified peer emits contract_certified=absent",
                        rec["contract_certified"] == "absent" and "delivery" in rec))

        # 7. A certified peer's delivery commit and artifact digests are consumed verbatim.
        pdir = ks / PEER_DIR / "p1" / "status"
        pdir.mkdir(parents=True)
        (pdir.parent / "status" / "KEYSTONE-PEER-REPORT.json").write_text(json.dumps({
            "verdict": "certified", "contract_version": "2.0-draft.1", "contract_digest": "d" * 64,
            "delivery": {"commit": "c" * 40, "tree_dirty": False,
                         "artifacts": {"peer_wheel": {"sha256": "a" * 64}}},
            "core_conformance": {"executed_check_set_digest": "e" * 64, "ok": True},
        }))
        rec2 = identity(ks, "p1", roster)
        planted.append(("a certified peer's commit + artifact sha256 are consumed verbatim",
                        rec2["contract_certified"] == "certified"
                        and rec2["delivery"]["commit"] == "c" * 40
                        and rec2["delivery"]["artifacts"]["peer_wheel"] == "a" * 64))

        # 8. ⛔ The overclaim guard: we consume ONE part of a five-part certification and say so.
        planted.append(("a certified record still declares which contract parts bore on us",
                        rec2["contract_parts_consumed"] == ["run"]))

        failed = [name for name, ok in planted if not ok]
        for name in failed:
            print(f"SELF-TEST FAILED: {name}", file=sys.stderr)
        if failed:
            return 1

    print(f"peer-binding self-test: OK — {len(planted)} planted control(s) held, including the "
          f"off-roster-name refusal, the roster floor, and the three-way distinction between an "
          f"absent spec_pin column, keystone's explicit `unknown`, and a real value")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--identity")
    ap.add_argument("--suite", default="py-prototype")
    ap.add_argument("--source", help="with --resolve: print just this source's peers, space-separated")
    ap.add_argument("--keystone", type=Path, default=ROOT.parent / "entity-core-keystone")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()
    if a.lint:
        return lint()
    try:
        if a.identity:
            print(json.dumps(identity(a.keystone, a.identity, read_roster(a.keystone)), indent=2))
            return 0
        if a.resolve:
            r = resolve(a.suite, a.keystone)
            if a.source:
                # The Makefile's consumer: the declared set, expanded, never a typed argument.
                print(" ".join(r["sources"].get(a.source, [])))
                return 1 if r["findings"] else 0
            for f in r["findings"]:
                print(f"  FINDING {f}", file=sys.stderr)
            print(json.dumps(r, indent=2))
            return 1 if r["findings"] else 0
    except GateError as exc:
        print(f"peer-binding: COULD NOT LOOK — {exc}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
