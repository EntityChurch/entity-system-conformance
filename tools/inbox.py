#!/usr/bin/env python3
"""The instrument that PULLS. AP-17's enforcement point.

WHY THIS EXISTS, because a tool whose incident is not written next to it gets deleted by the next
person who finds it noisy. Delivery in this polyrepo is: a counterpart commits a document to their
own tree and we read it. There is no notification and no queue. AGENTS-STANDARD says a packet
nobody enumerates is a packet nobody receives -- and for four sessions nothing on this side
enumerated. Four packets sat unrowed (AP-17). It recurred on 2026-09-16: five more, and one of them
carried a specification ruling that falsified a requirement we were about to hand to a fresh author.

⛔ THE DIRECTION OF THE ERROR IS THE WHOLE DESIGN. A packet we wrongly list is a minute wasted. A
packet we wrongly omit is an ask nobody answers, and it is INVISIBLE -- an empty inbox and an
unread inbox print the same thing. So every ambiguity here resolves toward listing it, and the
recipient parse is deliberately generous: a cc packed onto the `To:` line reads as a To.

WHAT IT DOES NOT DO, stated rather than left to inference:
  - It counts PACKETS, not asks. AGENTS.md is explicit that the asks inside a packet are what
    matter and there are usually several. Reading them is manual and this tool does not pretend
    otherwise -- it says `asks: unread` and that is a true statement about our knowledge.
  - `rowed` means the packet's full stem appears somewhere in a TRACKER file. That is a citation,
    not a discharge. A rowed packet may still be entirely unactioned.
  - It reads sibling trees READ-ONLY and never writes outside our own.
  - If the sibling directory cannot be read it says COULD NOT LOOK and exits 2. An empty result
    from an unreadable tree is the fail-open shape this repo refuses everywhere else.

⛔ WHERE A PACKET LIVES IS NOT ONE PLACE, AND ASSUMING IT WAS COST US A WHOLE COUNTERPART. This
tool globbed `docs/status/ROUTING-*.md` and nothing else. The routing standard then moved sent
packets to `docs/outbox/`, one counterpart adopted it and moved all of theirs, and the next run
printed `0 packet(s) addressed to us` -- a clean scan, in the shape a clean scan has, over a
directory that no longer held anything. The counterpart had not gone quiet; we had stopped
looking where they now write. So:
  - BOTH homes are globbed, always, and neither is ever assumed to be the live one.
  - A counterpart with NEITHER directory is reported by name as `no packet home` rather than
    contributing a silent zero. A repo that has never sent us anything and a repo whose packets
    we cannot see produce the same count and must not produce the same REPORT.
  - The sibling root is a LIST. It was one directory, which silently bounded the counterpart set
    to one parent -- a counterpart whose tree sits outside it was unreachable by construction,
    which is AP-1's bounded negative pointed at the counterpart list itself.

Usage:  python3 tools/inbox.py [--self-test] [--siblings DIR]... [--all] [--cc]
Exit:   0 nothing unrowed · 1 unrowed packets found · 2 could not look
"""
import argparse
import pathlib
import re
import sys

US = "entity-system-conformance"

# The addressee block is prose written by many hands and its shapes are real, sampled across the
# tree: backticked and bare; several `**To:**` lines; `From:` and `cc:` packed onto the To: line
# after an em dash, a middle dot or a parenthesis; and brace lists.
TO_LINE = re.compile(r"^\s*\*\*To:\*\*(.*)$", re.MULTILINE)
CC_LINE = re.compile(r"^\s*\*\*cc:\*\*(.*)$", re.MULTILINE)
# Anything from one of these separators onward is somebody else's field, not part of To.
TAIL = re.compile(r"(—|·|\(\s*cc\b|\bcc\s|\*\*From:\*\*|\*\*cc:\*\*| - cc\b)", re.IGNORECASE)
REPO = re.compile(r"[A-Za-z][A-Za-z0-9-]*(?:\{[a-z0-9,\s-]+\})?[A-Za-z0-9-]*")


def expand(name):
    """entity-core-{go,rust,py} -> the three names. A brace list is one line-item and three repos."""
    m = re.match(r"^(.*?)\{([^}]*)\}(.*)$", name)
    if not m:
        return [name]
    head, inner, tail = m.groups()
    return [f"{head}{p.strip()}{tail}" for p in inner.split(",") if p.strip()]


def recipients(text, pattern):
    out = []
    for raw in pattern.findall(text):
        head = TAIL.split(raw, maxsplit=1)[0]
        for tok in REPO.findall(head):
            out.extend(expand(tok))
    return out


def classify(text):
    """(addressed_to_us, cc_only). Generous on To by design -- see the header."""
    to = recipients(text, TO_LINE)
    cc = recipients(text, CC_LINE)
    return (US in to, US in cc and US not in to)


# The two homes a sent packet has. `docs/outbox/` is where the routing standard puts them;
# `docs/status/` is where they were before it, and where most of the cohort still writes.
# BOTH are globbed on every run. Dropping either one is the miss this tool already shipped once.
PACKET_HOMES = ("docs/outbox", "docs/status")


def scan(sibling_roots, tracker_dir, include_rowed=False):
    roots = [r for r in sibling_roots if r.is_dir()]
    missing_roots = [r for r in sibling_roots if not r.is_dir()]
    for r in missing_roots:
        print(f"inbox: COULD NOT LOOK — {r} is not a directory", file=sys.stderr)
    if not roots:
        return None
    rowed_text = ""
    for t in sorted(tracker_dir.glob("TRACKER-*.md")):
        rowed_text += t.read_text(encoding="utf-8", errors="replace")

    found, unreadable, homeless = [], [], []
    seen_repos = set()
    for root in roots:
        for repo in sorted(root.iterdir()):
            if not repo.is_dir() or repo.name == US or not (repo / ".git").exists():
                continue
            if repo.name in seen_repos:
                continue
            seen_repos.add(repo.name)
            homes = [repo / h for h in PACKET_HOMES if (repo / h).is_dir()]
            if not homes:
                # NOT a zero. A counterpart with no packet home is a counterpart we could not
                # look at, and it is named rather than folded into the clean count.
                homeless.append(repo.name)
                continue
            for home in homes:
                home_rel = home.relative_to(repo).as_posix()
                for pkt in sorted(home.glob("ROUTING-*.md")):
                    try:
                        text = pkt.read_text(encoding="utf-8", errors="replace")
                    except OSError as e:
                        unreadable.append(f"{pkt}: {e}")
                        continue
                    to_us, cc_us = classify(text)
                    if not (to_us or cc_us):
                        continue
                    stem = pkt.stem
                    is_rowed = stem in rowed_text
                    if is_rowed and not include_rowed:
                        continue
                    found.append({"stem": stem, "repo": repo.name,
                                  "home": home_rel, "to": to_us, "rowed": is_rowed})
    return found, unreadable, homeless, sorted(seen_repos), missing_roots


def report(found, unreadable, homeless, scanned, missing_roots, include_rowed, show_cc=False):
    for u in unreadable:
        print(f"  COULD NOT READ  {u}", file=sys.stderr)
    to_us = [f for f in found if f["to"]]
    cc_us = [f for f in found if not f["to"]]
    unrowed_to = [f for f in to_us if not f["rowed"]]

    if to_us:
        print("\n  ADDRESSED TO US:")
        for f in sorted(to_us, key=lambda r: r["stem"]):
            mark = "rowed  " if f["rowed"] else "UNROWED"
            print(f"    {mark}  {f['repo']}/{f['home']}/{f['stem']}   asks: unread")

    # cc is a real distinction: it says this is not addressed to you and you are not on the hook.
    # ⛔ Counted, never silently dropped -- a tool that omits a category without saying so reads as
    # "there were none". `--cc` lists them.
    if cc_us:
        if show_cc:
            print("\n  cc only — not on the hook:")
            for f in sorted(cc_us, key=lambda r: r["stem"]):
                mark = "rowed  " if f["rowed"] else "UNROWED"
                print(f"    {mark}  {f['repo']}/{f['home']}/{f['stem']}")
        else:
            print(f"\n  + {len(cc_us)} packet(s) cc us — not on the hook, not listed; `--cc` shows them")

    print(f"\ninbox: {len(to_us)} packet(s) addressed to us"
          + (f", {len(cc_us)} cc" if cc_us else "")
          + (" (rowed included)" if include_rowed else " unrowed")
          + f"   [{len(scanned)} counterpart(s) scanned, homes: {'/'.join(PACKET_HOMES)}]")

    # ⛔ The scope of the scan is part of the result. A count with no statement of what it ranged
    # over is the bounded negative this repo's own D15 refuses.
    if homeless:
        print(f"  ⚠ {len(homeless)} counterpart(s) have NEITHER {' nor '.join(PACKET_HOMES)} —"
              " not scanned, and NOT a zero:")
        print("     " + ", ".join(homeless))
    if missing_roots:
        print(f"  ⛔ {len(missing_roots)} sibling root(s) unreadable — every repo under them is"
              " unscanned and invisible to this count.")

    if unrowed_to:
        print(f"  ⛔ {len(unrowed_to)} addressed to us and on NO tracker. A packet nobody enumerates is a")
        print("     packet nobody receives. Row each one, then count THE ASKS INSIDE IT — the packet")
        print("     count is not the ask count and has never been.")
        return 1
    if unreadable or missing_roots:
        return 2
    print("  ⚠ `rowed` means the stem is cited on a tracker. That is a citation, not a discharge.")
    return 0


SELF_TEST = [
    # (name, packet text, expect_to_us, expect_cc_us)
    ("plain backticked To", "**To:** `entity-system-conformance`\n**From:** `x`\n", True, False),
    ("bare, no backticks", "**To:** entity-system-conformance\n", True, False),
    ("cc only is NOT to us", "**To:** `entity-core-go`\n**cc:** `entity-system-conformance`\n", False, True),
    ("cc packed after em dash is not a To for the cc'd repo",
     "**To:** `entity-core-go` — cc `entity-system-conformance`\n", False, False),
    ("cc packed in parens is not a To",
     "**To:** `entity-core-go` (cc `entity-system-conformance`)\n", False, False),
    ("From packed on the To line does not leak",
     "**To:** `entity-core-rust` · **From:** `entity-system-conformance`\n", False, False),
    ("brace list expands and includes us",
     "**To:** `entity-system-{conformance,generator}`\n", True, False),
    ("brace list that excludes us", "**To:** `entity-core-{go,rust,py}`\n", False, False),
    ("two To lines, we are the second",
     "**To:** `entity-browser-rust`\n**To:** `entity-system-conformance`\n", True, False),
    ("a mention in the body is not an addressee",
     "**To:** `entity-core-go`\n**cc:** —\n\nWe read entity-system-conformance's tree.\n", False, False),
    ("multi-repo cc list including us",
     "**To:** `entity-core-go`\n**cc:** `entity-core-rust`, `entity-system-conformance`\n", False, True),
    ("a near-name must not match", "**To:** `entity-system-conformance-archive`\n", False, False),
]


def _quiet(fn):
    import contextlib
    import io
    with contextlib.redirect_stderr(io.StringIO()):
        return fn()


def discovery_self_test():
    """The half the parser controls above cannot reach, and the half that actually failed.

    Every control in SELF_TEST held on the day this tool reported a clean scan over a counterpart
    who had moved every one of their packets to `docs/outbox/`. `classify` was never wrong. WHICH
    DIRECTORIES GET GLOBBED was, and nothing measured it -- so these plant a packet in each home
    and assert it is found, and plant a counterpart with no home at all and assert it is NAMED
    rather than counted as zero.
    """
    import tempfile
    TO_US = "**To:** `entity-system-conformance`\n**From:** `x`\n**Tip:** `dev` @ `0000000`\n"
    cases, bad = [], 0
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td) / "siblings"
        for repo, home in (("peer-outbox", "docs/outbox"), ("peer-status", "docs/status")):
            d = root / repo / home
            d.mkdir(parents=True)
            (root / repo / ".git").mkdir()
            (d / "ROUTING-2026-09-17-a-entity-system-conformance-planted.md").write_text(TO_US)
        (root / "peer-homeless" / "docs").mkdir(parents=True)
        (root / "peer-homeless" / ".git").mkdir()
        (root / "not-a-repo").mkdir()          # no .git — not a counterpart, must not be named
        trackers = pathlib.Path(td) / "trackers"
        trackers.mkdir()

        found, unreadable, homeless, scanned, missing = scan([root], trackers)
        homes_found = {f["home"] for f in found if f["to"]}
        cases = [
            ("a packet in docs/outbox/ is found", "docs/outbox" in homes_found),
            ("a packet in docs/status/ is still found", "docs/status" in homes_found),
            ("both homes are globbed in one run", len([f for f in found if f["to"]]) == 2),
            ("a counterpart with no packet home is NAMED, not a silent zero",
             homeless == ["peer-homeless"]),
            ("a directory that is not a git repo is not counted as a counterpart",
             "not-a-repo" not in scanned and "not-a-repo" not in homeless),
            # Its COULD NOT LOOK goes to stderr by design; muted here so a PASSING control does
            # not print in the shape of a failure.
            ("an unreadable sibling root is could-not-look, never clean",
             _quiet(lambda: scan([root / "does-not-exist"], trackers)) is None),
        ]
    for name, ok in cases:
        if not ok:
            print(f"  FAIL  {name}", file=sys.stderr)
            bad += 1
    return bad, len(cases)


def self_test():
    bad = 0
    for name, text, exp_to, exp_cc in SELF_TEST:
        got_to, got_cc = classify(text)
        if (got_to, got_cc) != (exp_to, exp_cc):
            print(f"  FAIL  {name}: expected to={exp_to} cc={exp_cc}, got to={got_to} cc={got_cc}",
                  file=sys.stderr)
            bad += 1
    dbad, dtotal = discovery_self_test()
    bad += dbad
    total = len(SELF_TEST) + dtotal
    if bad:
        print(f"inbox self-test: {bad} of {total} control(s) FAILED", file=sys.stderr)
        return 1
    print(f"inbox self-test: OK — {total} control(s) held: {len(SELF_TEST)} on the addressee parse,"
          " including the four shapes that pack cc or From onto the To: line (a cc read as a To"
          " over-reports; a To read as a cc LOSES an ask, so the controls pin both directions);"
          f" and {dtotal} on DISCOVERY, which is the half that failed — both packet homes globbed,"
          " a counterpart with neither named rather than counted as zero, an unreadable root"
          " could-not-look")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    # A LIST, and repeatable. One root silently bounds the counterpart set to one parent
    # directory, and a counterpart outside it is not "quiet" -- it is unreachable by construction.
    ap.add_argument("--siblings", type=pathlib.Path, action="append", default=None,
                    help="a directory holding sibling repos; repeatable (default: ..)")
    ap.add_argument("--all", action="store_true", help="list rowed packets too, not only unrowed")
    ap.add_argument("--cc", action="store_true", help="list the cc packets as well as counting them")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    roots = [p.resolve() for p in (a.siblings or [pathlib.Path("..")])]
    res = scan(roots, pathlib.Path("docs/status"), include_rowed=a.all)
    if res is None:
        return 2
    return report(*res, a.all, a.cc)


if __name__ == "__main__":
    sys.exit(main())
