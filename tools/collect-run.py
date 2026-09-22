#!/usr/bin/env python3
"""collect-run — file one instrument's per-peer reports under output/runs/, WITH the posture they ran in.

    tools/collect-run.py keystone --instrument s1-py --src <dir> --keystone <tree> --out output/runs PEER...
    tools/collect-run.py core-go  --instrument validate-peer --src <dir> --posture-file output/peer-up.posture --out output/runs PEER...

Writes, per peer:  <out>/<source>/<instrument>/<peer>.json            the report, verbatim
                   <out>/<source>/<instrument>/<peer>.provenance.json  where it came from + the posture

WHY THE POSTURE IS COLLECTED HERE AND NOT BY THE INSTRUMENT. Under keystone's census the instrument is
exec'd by the peer's own harness with fixed argv; it cannot be told what the harness launched the peer
with. So the declaration is read from the harness itself — the launch line in that peer's run-s4.sh,
quoted, with the file's sha256 — rather than typed from memory. A posture typed by hand is the
undeclared posture with extra steps.

For core-go the posture is the record `make peer-up` wrote when it launched the peer (--posture-file). It is
never typed here: until 2026-09-13 this file hard-coded "bootstrap-default" whatever the peer had been given.

REFUSES a report older than --max-age-s (default 6h), one whose file is missing, and a core-go collection with no
posture record: could-not-look is exit 2, never a silently shorter run or a guessed posture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git_head(tree: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True).stdout.strip()
        return out.stdout.strip() + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def tree_state(tree: Path, paths: list[str]) -> dict:
    """WHICH BUILD of the peer was measured: HEAD, plus a digest of the uncommitted diff under the peer's own paths.
    Added 2026-09-13 (F50): another session edited Keystone's rust peer mid-run, and the oracle and the suite measured
    two different builds while the posture key — launch lines only — called them comparable."""
    try:
        head = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        diff = subprocess.run(["git", "-C", str(tree), "diff", "HEAD", "--", *paths], capture_output=True, check=True).stdout
        untracked = subprocess.run(["git", "-C", str(tree), "ls-files", "--others", "--exclude-standard", "--", *paths],
                                   capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"head": "unknown", "diff_sha256": "unknown"}
    return {"head": head, "paths": paths,
            "diff_sha256": hashlib.sha256(diff + b"\0" + untracked).hexdigest() if (diff or untracked) else "clean"}


LAUNCH = re.compile(r"(--debug-open-grants|--seed-policy|--open-access|-open-access|--validate|--port)")


def keystone_posture(tree: Path, peer: str) -> dict:
    harness = tree / "protocol-generator" / peer / "run-s4.sh"
    if not harness.is_file():
        return {"declared": False, "why": f"no harness at {harness}"}
    lines = [l.strip() for l in harness.read_text().splitlines()
             if LAUNCH.search(l) and not l.lstrip().startswith("#")]
    text = " ".join(lines)
    grants = ("debug-open-grants" if "--debug-open-grants" in text
              else "seed-policy" if "--seed-policy" in text else "unknown — read launch_lines")
    prov = tree / "output" / "s4-oracles" / "PROVENANCE.txt"
    oracle = {}
    if prov.is_file():
        for l in prov.read_text().splitlines():
            if "=" in l and not l.startswith("#"):
                k, v = l.split("=", 1)
                oracle[k.strip()] = v.split("#")[0].strip()
    return {
        "declared": True,
        "source": f"entity-core-keystone protocol-generator/{peer}/run-s4.sh (read at collection)",
        "grants": grants,
        "launch_lines": lines,
        "harness_sha256": sha256(harness),
        "keystone_head": git_head(tree),
        "peer_tree": tree_state(tree, [f"protocol-generator/{peer}"]),
        "keystone_installed_oracle": {k: oracle.get(k) for k in ("commit", "core_gate_fingerprint", "check_set_digest")},
    }


def generator_posture(tree: Path, target: str, comp: str) -> dict:
    """The launch flags live in tools/host-launch (shared) plus languages/<t>/host-entry (per target)."""
    files = [tree / "tools" / "host-launch", tree / "languages" / target / "host-entry"]
    lines = []
    for f in files:
        if f.is_file():
            lines += [f"{f.name}: {l.strip()}" for l in f.read_text().splitlines()
                      if LAUNCH.search(l) and not l.lstrip().startswith("#")]
    text = " ".join(lines)
    grants = ("debug-open-grants" if "--debug-open-grants" in text
              else "seed-policy" if "--seed-policy" in text else "unknown — read launch_lines")
    return {"declared": True, "source": f"entity-system-generator tools/host-launch + languages/{target}/host-entry (read at collection)",
            "grants": grants, "composition": comp, "launch_lines": lines,
            "harness_sha256": "+".join(sha256(f)[:16] for f in files if f.is_file()),
            "generator_head": git_head(tree),
            "peer_tree": tree_state(tree, [f"languages/{target}", "tools/host-launch"])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=["keystone", "core-go", "generator"])
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--keystone", type=Path)
    ap.add_argument("--posture-file", type=Path, help="core-go: the record make peer-up wrote at launch")
    ap.add_argument("--generator", type=Path)
    ap.add_argument("--comp")
    ap.add_argument("--max-age-s", type=int, default=6 * 3600,
                    help="refuse a report older than this; a stale report read as fresh is the census's own recorded defect")
    ap.add_argument("peers", nargs="+")
    a = ap.parse_args()

    dest = a.out / a.source / a.instrument
    dest.mkdir(parents=True, exist_ok=True)
    missing = 0
    for peer in a.peers:
        src = a.src / f"{peer}.json"
        if not src.is_file():
            print(f"collect-run: {a.source}/{a.instrument}/{peer}: NO REPORT at {src}", file=sys.stderr)
            missing += 1
            continue
        age = time.time() - src.stat().st_mtime
        if age > a.max_age_s:
            print(f"collect-run: {a.source}/{a.instrument}/{peer}: STALE — report is {age/3600:.1f}h old", file=sys.stderr)
            missing += 1
            continue
        out = dest / f"{peer}.json"
        if src.resolve() != out.resolve():
            shutil.copyfile(src, out)
        if a.source == "keystone":
            posture = keystone_posture(a.keystone, peer)
        elif a.source == "generator":
            posture = generator_posture(a.generator, peer.rsplit("-", 1)[0], a.comp)
        else:
            if not a.posture_file or not a.posture_file.is_file():
                print(f"collect-run: core-go/{a.instrument}/{peer}: COULD NOT LOOK — no posture record "
                      f"({a.posture_file}); make peer-up writes it", file=sys.stderr)
                return 2
            rec = dict(l.split("=", 1) for l in a.posture_file.read_text().splitlines() if "=" in l)
            if rec.get("started_at", "0").isdigit() and int(rec["started_at"]) > src.stat().st_mtime:
                print(f"collect-run: core-go/{a.instrument}/{peer}: REFUSING — the peer was relaunched after this report "
                      f"was written, so the posture record is not this report's", file=sys.stderr)
                return 2
            posture = {"declared": True, "source": f"entity-system-conformance make peer-up ({a.posture_file}, read at collection)",
                       "grants": rec.get("grants", "unknown"),
                       # WHAT was launched, not WHEN: a relaunch of the same image and arguments is the same posture.
                       "harness_sha256": hashlib.sha256("\n".join(f"{k}={v}" for k, v in sorted(rec.items())
                                                                   if k != "started_at").encode()).hexdigest(),
                       **rec}
        prov = {"source": a.source, "instrument": a.instrument, "peer": peer,
                "report_sha256": sha256(out), "report_mtime": int(src.stat().st_mtime),
                "collected_at": int(time.time()), "posture": posture}
        (dest / f"{peer}.provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
        r = json.loads(out.read_text())
        print(f"collect-run: {a.source}/{a.instrument}/{peer}: {r.get('summary')}  posture grants={posture.get('grants')}")
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
