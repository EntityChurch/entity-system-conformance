#!/usr/bin/env python3
"""differential — every instrument that ran on a peer, joined by REQUIREMENT ID.

    tools/differential.py --runs output/runs --requirements requirements/core --out output/DIFFERENTIAL.md

Reads output/runs/<source>/<instrument>/<peer>.json (+ .provenance.json). `validate-peer` is the reference
oracle; every other instrument directory is a suite of ours, and there may be any number of them (AGENTS.md,
the multi-suite model). Nothing here knows a suite by name.

Two kinds of comparison, both keyed by requirement id:
  suite  vs oracle  — the oracle has no requirement ids, so each requirement is joined to the check its OWN
                      file names (`notes.oracle_check`, provenance only). The join key comes from our file,
                      never the oracle, so a renamed check shows up as `absent` rather than dropping out.
  suite  vs suite   — direct: both report requirement ids.

Classes — and none of them is resolved by re-running:
  AGREE           both accept the peer, or both refuse it
  DISAGREE        one accepts and the other refuses. The product. Triage: spec gap | impl bug | check bug
  NOT COMPARABLE  either side SKIPped / INCONCLUSIVE, the named check is absent, or the POSTURE or PEER BUILD differs
  ORACLE BLIND    our requirement names NO oracle check: the oracle does not measure this obligation at all. A FAIL
                  here is the shape this seat exists for — a cohort behaviour nothing else would ever score

A status document for the next session, not a verdict: every DISAGREE row is `untriaged` until someone reads
both instruments' messages against the spec.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ORACLE = "validate-peer"


def oracle_map(req_dir: Path) -> dict[str, list[str]]:
    out = {}
    for p in sorted(req_dir.glob("*.toml")):
        req = tomllib.loads(p.read_text())["requirement"]
        rid = req.get("id") or p.stem
        oc = str(req.get("notes", {}).get("oracle_check", ""))
        out[rid] = [c.strip() for c in oc.replace(";", ",").split(",") if c.strip()]
    return out


def accepts(verdict: str | None) -> bool | None:
    """True = the instrument accepts the peer on this row, False = refuses, None = no comparable verdict."""
    if verdict in ("PASS", "WARN"):
        return True
    if verdict == "FAIL":
        return False
    return None


def classify(a: str | None, b: str | None, same_posture: bool) -> str:
    if a is None or b is None:
        return "NOT COMPARABLE (absent)"
    if not same_posture:
        return "NOT COMPARABLE (posture or peer build)"
    x, y = accepts(a), accepts(b)
    if x is None or y is None:
        return f"NOT COMPARABLE ({a}/{b})"
    return "AGREE" if x == y else "**DISAGREE** — untriaged"


def load(d: Path, peer: str):
    p = d / f"{peer}.json"
    if not p.is_file():
        return None, {}
    prov = d / f"{peer}.provenance.json"
    return json.loads(p.read_text()), (json.loads(prov.read_text()) if prov.is_file() else {})


def posture_key(prov: dict) -> tuple:
    """Two reports are comparable only if the same posture was launched against the same BUILD of the peer: grants,
    the launching harness, and the peer's source state (HEAD + uncommitted diff under its paths, F50)."""
    p = prov.get("posture", {})
    t = p.get("peer_tree") or {}
    return (p.get("grants"), p.get("harness_sha256"), t.get("head"), t.get("diff_sha256"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--requirements", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    omap = oracle_map(a.requirements)
    body: list[str] = []
    totals: dict[str, dict[str, int]] = {}
    executed: dict[str, set[str]] = {}
    pairs = 0

    def tally(pair: str, cls: str):
        key = cls.strip("*")
        key = key if key.startswith("ORACLE BLIND") else key.split(" (")[0].split("** —")[0].split(" —")[0]
        totals.setdefault(pair, {}).setdefault(key, 0)
        totals[pair][key] += 1

    for source_dir in sorted(p for p in a.runs.iterdir() if p.is_dir()):
        suites = sorted(p.name for p in source_dir.iterdir() if p.is_dir() and p.name != ORACLE)
        peers = sorted({f.stem for s in suites for f in (source_dir / s).glob("*.json") if not f.name.endswith(".provenance.json")})
        for peer in peers:
            pairs += 1
            reports = {s: load(source_dir / s, peer) for s in suites}
            reports = {s: r for s, r in reports.items() if r[0] is not None}
            vp, vp_prov = load(source_dir / ORACLE, peer)
            checks = {f"{c['category']}/{c['name']}": c for c in (vp or {}).get("checks", [])}
            body += [f"## {source_dir.name} / {peer}", ""]
            for s, (r, prov) in reports.items():
                body.append(f"- {s}: `{r.get('summary')}` · report sha256 `{prov.get('report_sha256', '?')[:16]}…` · "
                            f"signs `{r.get('sign_message')}` · posture `{prov.get('posture', {}).get('grants')}`")
            body.append(f"- {ORACLE}: " + (f"`{ {k: vp['summary'].get(k) for k in ('total', 'passed', 'warned', 'failed', 'skipped')} }` · report sha256 "
                                           f"`{vp_prov.get('report_sha256', '?')[:16]}…` · posture `{vp_prov.get('posture', {}).get('grants')}`"
                                           if vp else "**no report — nothing to compare**"))
            verdicts = {s: {x["requirement_id"]: x for x in r.get("results", [])} for s, (r, _) in reports.items()}
            for s, v in verdicts.items():
                executed.setdefault(s, set()).update(k for k, x in v.items() if x.get("suite_check") != "suite-error")
            rids = sorted({rid for v in verdicts.values() for rid in v}, key=lambda x: (len(x), x))

            head = "| requirement | " + " | ".join(suites) + " | oracle check | " + ORACLE + " | " + \
                   " | ".join(f"{s} vs oracle" for s in suites) + (" | " + " | ".join(f"{x} vs {y}" for i, x in enumerate(suites) for y in suites[i + 1:]) if len(suites) > 1 else "") + " |"
            body += ["", head, "|" + "---|" * (head.count("|") - 1)]
            for rid in rids:
                for oc in omap.get(rid, []) or ["—"]:
                    c = checks.get(oc)
                    theirs = c["severity"] if c else None
                    row = [f"`{rid}`"] + [verdicts[s].get(rid, {}).get("verdict", "—") for s in suites] + [f"`{oc}`", theirs or "absent"]
                    for s in suites:
                        ours = verdicts[s].get(rid, {}).get("verdict")
                        same = vp is not None and posture_key(reports[s][1]) == posture_key(vp_prov)
                        if not ours:
                            cls = "—"
                        elif oc == "—":
                            cls = f"ORACLE BLIND ({ours})" if ours != "FAIL" else "**ORACLE BLIND (FAIL)**"
                        else:
                            cls = classify(ours, theirs, same)
                        if ours:
                            tally(f"{s} vs {ORACLE}", cls)
                        row.append(cls)
                    for i, x in enumerate(suites):
                        for y in suites[i + 1:]:
                            vx, vy = verdicts[x].get(rid, {}).get("verdict"), verdicts[y].get(rid, {}).get("verdict")
                            same = posture_key(reports[x][1]) == posture_key(reports[y][1])
                            cls = classify(vx, vy, same)
                            if vx and vy and oc == (omap.get(rid) or ["—"])[0]:
                                tally(f"{x} vs {y}", cls)
                            row.append(cls)
                    body.append("| " + " | ".join(row) + " |")

            joined = {oc for rid in rids for oc in omap.get(rid, [])}
            cats = {oc.split("/")[0] for oc in joined}
            unjoined = sorted((k, c["severity"]) for k, c in checks.items() if k.split("/")[0] in cats and k not in joined)
            if vp:
                body += ["", f"**Coverage:** the oracle executed {len(unjoined) + len(joined & set(checks))} checks in "
                         f"{', '.join(sorted(cats))}; {len(joined & set(checks))} are joined to a requirement a suite ran, "
                         f"**{len(unjoined)} have no requirement here** — " + ", ".join(f"`{k.split('/', 1)[1]}` {sev}" for k, sev in unjoined)]
            for s, v in verdicts.items():
                for rid, x in v.items():
                    if x["verdict"] == "PASS" and not x.get("witnesses"):
                        continue
                    body += ["", f"<details><summary><code>{s}</code> <code>{rid}</code> {x['verdict']}: {x['message'][:160]}</summary>", ""]
                    for arm in x.get("arms", []):
                        held = {True: "held", False: "**NOT HELD**", None: "n/a"}[arm["held"]]
                        body.append(f"- {arm['kind']} `{arm['name']}` {held} — {arm['outcome']}")
                    for k, w in (x.get("witnesses") or {}).items():
                        body.append(f"- witness `{k}`: {str(w)[:300]}")
                    for oc in omap.get(rid, []):
                        if oc in checks:
                            body.append(f"- oracle `{oc}` {checks[oc]['severity']}: {checks[oc].get('message', '')[:300]}")
                    body += ["", "</details>"]
            body.append("")

    lines = ["# DIFFERENTIAL — every instrument, by requirement id", "",
             "Generated by `make differential`. Internal run artifact (output/ is not committed); cite by report sha256.", "",
             f"**{pairs} peer runs.**", ""]
    for pair, t in sorted(totals.items()):
        lines.append(f"- **{pair}:** " + " · ".join(f"{k} {v}" for k, v in sorted(t.items())))
    lines += ["", "**Joint coverage (requirement ids executed):** " + " · ".join(f"{s} {len(v)}" for s, v in sorted(executed.items()))
              + f" · together {len(set().union(*executed.values())) if executed else 0}", ""]
    a.out.write_text("\n".join(lines + body) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
