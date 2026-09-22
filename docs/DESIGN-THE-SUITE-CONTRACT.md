# DESIGN — the suite contract: how a suite is invoked, and what it emits

**Status:** first cut, written by the architecture seat during bring-up. **Not ratified**, and it is
the half that needs agreement from three other seats before it is worth much.
**Why it matters more than the format:** the requirement format is ours alone. **This is the
interface a consumer swaps across**, so if it is wrong, "pluggable" is a word rather than a fact.

---

## 0. The test this contract has to pass

> **A consumer can run suite A or suite B, compare the results, and localize a disagreement — without
> either suite's internals appearing anywhere in the consumer's tree.**

Today that fails on all three counts, measured: consumers pin **431 oracle check names** (344 gate
baselines + 87 coverage rows in the most coupled tree), they call a specific CLI, and they parse a
report whose shape is specified nowhere. Any of those alone makes a swap a rewrite.

---

## 1. Invocation — the minimum any suite accepts

Derived from the reference oracle's live flag set, generalized. **The names are inherited
deliberately** — renaming them to win a coupling argument would invalidate every published
conformance number in the ecosystem, and the coupling that matters is expected values, not spelling.

| Flag | Meaning |
|---|---|
| `--addr <host:port>` | the peer under test |
| `--profile <core\|full>` | which requirement set |
| `--requirements <id,…>` / `--category <name>` | scope the run |
| `--peer <label>=<addr>` *(repeatable)* | ⭐ **counterparties for cross-peer requirements — see §3** |
| `--json-out <path>` | the verdict document (§2) |
| `--posture <file>` | ⭐ **the declared fixture posture — see §4** |
| `--allow-skip <id,…>` | intentional skips, declared |
| `--list-requirements` | what this suite implements, machine-readable |

**`--list-requirements` is the one with no precedent and it is what makes joint coverage possible.**
It answers *"which requirements does this suite cover?"* without running anything, so
*"suite A reaches 24 of 38 binding rows, suite B reaches 19, together 31"* becomes computable. **No
existing instrument can answer it.**

---

## 2. The verdict document — and six of its fields do not exist today

`PROPOSAL-CONFORMANCE-ORACLE-CONTRACT` §4 already specifies this. **Measured against the reference
oracle's report struct as it stood when this document was written — read it again before relying on
the list, since it is the one input here that moves without telling us. It carries** `peer_addr` ·
`peer_id` · `peers` · `timestamp` ·
`summary` · `checks` · `declared_exclusions` — **and no oracle identity, no check-set digest, no
profile, no spec version, no requirement id and no posture.**

Two consequences, and the second is the tell:

- `[ADR-0012]`'s citation form is specified as *"derived from this document, not typed by hand."*
  **It cannot be. The inputs are absent.**
- **The consumer built the producer's identity in its own tree.** `entity-core-keystone` ships
  `core_executed_check_set_digest` and, in **its** tooling rather than ours, a check-set gate that refuses to place two peers
  in one column unless both reports carry it. *When a consumer has to reconstruct a producer's
  identity to compare two of its outputs, the missing field is a specification defect — not a
  downstream inconvenience.*

```jsonc
{
  "suite":    { "name": "...", "version": "...", "commit": "..." },
  "spec":     { "version": "0.8.2.21", "snapshot_digest": "sha256:..." },
  "profile":  "core",
  "requirement_set_digest": "sha256:...",   // what was RUN. the comparability anchor
  "posture":  { /* §4 — verbatim, as data */ },
  "peers":    [ { "label": "subject", "addr": "...", "peer_id": "..." },
                { "label": "counterparty", "addr": "...", "peer_id": "..." } ],
  "summary":  { "total": 0, "passed": 0, "warned": 0, "failed": 0, "skipped": 0,
                "peer_attributable": 0 },
  "results":  [ {
      "requirement_id": "RB-R1",            // ⭐ THE JOIN KEY. not the check name
      "suite_check":    "resource_bounds/r1_payload_over_limit",  // provenance only
      "verdict":        "PASS",             // PASS | WARN | FAIL | SKIP
      "spec_ref":       "ENTITY-CORE-PROTOCOL §4.10(a)",
      "peer_attributable": true,
      "domain_member":  null,               // set when the requirement is enumerated
      "message":        "..."
  } ]
}
```

**Four rules on it:**

1. **`requirement_id` is the join key.** A result without one cannot be compared to another suite's
   and is, for cross-suite purposes, noise.
2. **`SKIP` names the reason and the surface not reached.** A skip counts as a failure for release
   purposes (`[ADR-0012]`) — **it is never quietly a pass.**
3. **Fail closed on could-not-look.** A suite that could not reach a surface **MUST NOT** report a
   pass for it. *"Could not look" and "looked and found nothing" are different results*, and
   collapsing them is the single most repeated instrument defect in this ecosystem.
4. **`peer_attributable` is per result.** A check the peer was never asked about does not score the
   peer — see the export's §4 for the worked case where four core-profile rows measured the oracle's
   own libraries.

---

## 3. Cross-peer requirements — the pair is a parameter

`--peer <label>=<addr>` is repeatable, and a cross-peer requirement names the **roles** it needs, not
the implementations. **Any peer clearing the floor is a candidate for either end.**

- The verdict records **which two peers** produced each cross-peer result.
- Where the full matrix is not run — and it will not be, it is N² — **the pairs that WERE run are
  declared.** *An undeclared sample of a matrix is the same defect as an undeclared posture: an
  input that decides the outcome, chosen once, by one party, never written down.*

⛔ **The open design question this leaves, and it is the first hard one this repo owns:** which
pairs, chosen how, re-chosen how often. A rotating subset, a fixed diverse set, and full-matrix-on-
release are all defensible; none has been argued yet.

---

## 4. The posture document

```toml
[posture]
name = "floor"      # the §6.9a bootstrap default, no wide debug grant
[posture.grants]
default = "discovery-floor"
[posture.identities]
owner = "self-signed"
```

**Why this is a first-class input rather than launcher trivia.** One peer run twice — once as the
ecosystem has always run it, once on the specification's own bootstrap default — **changed the SIZE
of the check set**: 778 → 717, with 54 severities moving, every one downward, including every
`universal_address_space` check and every `core_register_*` check, both core-profile. Under
`[ADR-0012]` that is 47 failures.

> **Two runs under different postures are not a better and a worse number. They are not comparable
> measurements.** And every published figure in the ecosystem was produced in one posture that no
> document names — not from carelessness, but because **there was no field to write it in.**

**A suite refuses to emit a verdict without a posture.** That is cheap now and impossible to
retrofit once numbers are circulating.

---

## 5. What we need from other seats

**None of this is ours to impose, and three of the four are somebody else's tree.**

| # | Seat | Ask |
|---|---|---|
| 1 | `entity-core-go` | **§2's six fields** in the report, and a `check → requirement_id` map. *Everything else here degrades gracefully; without this, a differential is impossible.* |
| 2 | `entity-core-go` | **§3** — `origination`'s counterparty becomes a parameter |
| 3 | `entity-core-keystone` · `entity-system-generator` | **key gates and baselines to `requirement_id`.** 431 pinned check names today; a swap reds all of them at once, and *the reasonable response to a false red across a whole tree is to delete the baselines* |
| 4 | `entity-system-architecture` | ratify the contract; sweep `spec inventory` (**1 of 26**) so extension requirements are addressable |

**Ask 3 pays for itself before any second suite exists** — today a re-pin that renames a check
silently invalidates a baseline. It is the one to lead with.

---

## 6. What this contract deliberately does not specify

- **A suite's internals.** Language, runner, concurrency, how it talks to a peer. *The whole point
  is that two suites share nothing but the requirement set and this contract.*
- **How a suite is built or tested.** Its own concern.
- **Who is right when two suites disagree.** That is the architecture seat's, by ruling. **This
  contract's only job is to make the disagreement legible enough to adjudicate** — and that is why
  `requirement_id` and `posture` are mandatory and everything else is negotiable.
