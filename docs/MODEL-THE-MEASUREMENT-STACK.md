# MODEL — the measurement stack: who measures whom, and where each layer's oracle problem is solved

**What this is.** The one place that says what sits on what. Every other document here describes a
*part* — `README.md` the threat model, `docs/PROCESS.md` the method, `WORKFLOW-SUITE-BRINGUP.md` the procedure, the
requirement/item split, the `RUN-*` records the measurements. **None of them says what the whole
thing is shaped like**, and the argument this seat rests on is a claim about that shape: *a single
oracle cannot distinguish "the peer is wrong" from "the oracle is wrong."* That claim is only
checkable against a map.

**Why it did not exist until 2026-09-16 (d).** Because every fragment of it was true where it was
written. The layer counts, the generation-lineage caveats, the *"we are Kind C by construction"*
line, the three controls — all present, all scattered, and **no document owned the join.** A model
distributed across twelve files is not a model; it is a set of local claims nobody has checked
against each other, which is the same failure mode as a chain of tight pins with a loose anchor.

⛔ **This document is descriptive, not normative.** It does not decide anything. Where it disagrees
with this repository's charter or one of its architecture decisions, they win and this file is wrong.

---

## 1. The stack

```
  ┌────────────────────────────────────────────────────────────────────────────────┐
  │  L0   THE SPECIFICATION            entity-core-protocol                        │
  │       one author (arch seat) · 0.8.2.29 committed, .30 in flight               │
  │       ⛔ OUR PIN IS v0.8.2.26 — three revisions behind                          │
  └────────────────────────────────────────────────────────────────────────────────┘
        │ implemented by                        │ modelled by
        ▼                                       ▼
  ┌──────────────────────────────────┐   ┌────────────────────────────────┐
  │ L1  IMPLEMENTATIONS (peers)      │   │ L0′ FORMAL MODELS              │
  │  3 ground-up   entity-core-{go,  │   │  entity-core-formalization     │
  │                rust,py}          │   │  a partial second opinion on   │
  │  46 generated  keystone cohort   │   │  L0 — it proves about the text │
  │  N composed    generator peers   │   │  rather than measuring a peer  │
  └──────────────────────────────────┘   └────────────────────────────────┘
        │ scored by
        ▼
  ┌────────────────────────────────────────────────────────────────────────────────┐
  │  L2   INSTRUMENTS — three, and that is the whole point                         │
  │   (a) validate-peer        entity-core-go · the reference oracle · PERMANENT   │
  │   (b) suites/py-prototype  ours · suite 1 · Python · 28 of 50 executed         │
  │   (c) suites/rs-conformance ours · suite 2 · Rust, zero deps · 3 of 50         │
  │       built by an author who had not read (b). Shares no code, codec,          │
  │       crypto or language with it. First comparison: AGREE 2, NOT COMPARABLE 1  │
  │       joined on REQUIREMENT ID by `make differential` — never on check names   │
  └────────────────────────────────────────────────────────────────────────────────┘
        │ scored by
        ▼
  ┌────────────────────────────────────────────────────────────────────────────────┐
  │  L3   WHAT CHECKS THE INSTRUMENTS — the regress, and where it stops            │
  │   A  constructed positive   per probe · independent of everything   ✅ SOLID   │
  │   B  known-arm peer set     CONTROL-SET.diag · not independent of us  ✅       │
  │   C  external fixture       RFC 8032 · RFC 8949 · the normative corpus ✅      │
  │   D  the other instrument   validate-peer, pointed at us                       │
  └────────────────────────────────────────────────────────────────────────────────┘
```

**The stack is four layers and it is not symmetric.** L0 has one author. L1 has many
implementations but far less independence than the count suggests (§3). L2 has three instruments,
two of them ours, and the second of ours reaches three requirements — so the *joint* coverage is
still one instrument deep almost everywhere. L3 is not a layer of *artifacts* at all — it is four different arguments, and only two
of them reach outside this ecosystem.

---

## 2. The propagation rule — why any of this matters

> **A defect at layer N is canonicalized by layer N+1, because N+1 fixes everything until it
> agrees.**

This is the threat model in `README.md` stated as a general law rather than as a fact about one oracle:

| Defect in | Becomes | Because |
|---|---|---|
| **L0** the spec | every implementation's behaviour | implementers implement what it says |
| **L1** one peer | nothing, if caught | ⇒ this is the *cheap* case and the only one the ecosystem is good at |
| **L1** the **generator** | a correlated defect in 46 peers that reads as convergence | §3 |
| **L2** an instrument | every peer is "fixed" until it passes ⇒ the bug becomes the protocol | the founding argument |
| **L3** a control | an instrument that is wrong and *verified* wrong | nothing above it looks |

⭐ **The rows get worse going up, and the effort in this ecosystem is concentrated at the bottom.**
That asymmetry is the entire reason this seat exists, and it is also why *"we ran 40 peers instead
of 4"* is not progress: it is more evidence at the layer where evidence is already cheap.

⛔ **And L2 defects arrive through documents, not only through code.** On 2026-09-16 (c) the
falsified `ECP-R3` reading reached `docs/BRIEF-SUITE-2.md` and `suites/CONTROL-SET.diag`, which
would have handed a *fresh* instrument the error by hand — **propagation with the code step skipped
entirely.** An onboarding document has no reviewer by construction. Treat it as instrument surface.

---

## 3. ⭐⭐ The independence ledger — every "independent" claim, and whether it holds

**This is the most important table here.** The stack's value is entirely a function of which
independence claims are real, and the counts flatter us everywhere.

| Claim | Real? | What actually holds |
|---|---|---|
| **3 ground-up implementations** (`go`, `rust`, `py`) | ✅ **YES** | Separate code bases, separate authors. Agreement between these three is real evidence. |
| **46 keystone peers** | ⛔ **NO — one lineage** | Generated from one generator by one seat. A generator defect is 46 correlated failures that *look* like 46 confirmations. **Cohort-consistent, not independent convergence** — the ecosystem's own phrase. |
| **N generator-composed peers** | ⛔ **NO — one lineage** | Same shape, different tool. Three of our four control peers are these, and they returned **identical results on all 28 requirements.** |
| **40 declared peers** in our set | ⚠ **misleading** | 36 keystone (one lineage) + 3 generator (one lineage) + 1 core-go. **By lineage that is three sources, not forty.** |
| **2 instruments at L2** | ⚠ **partial** | `validate-peer` is authored by the same seat as the reference peer, in the same language, with the same crypto library. Ours is deliberately not — **but suite 1's first draft was Go with `crypto/ed25519`, agreed beautifully, and was thrown away** (`AP-10`). The separation is real *now* and it was bought, not inherited. |
| **suite 2 independent of suite 1** | ⚠ **PARTIAL, AND THE BREACH IS DECLARED** | Suite 2 exists. Language, codec, crypto and dependency independence are real and gated (`lint-suite-independence`); the author built from the pinned spec text and three obligation files, and read neither suite 1's source nor the control set. ⛔ **What is not clean: the agent harness injects this repo's operating guide into an author's context before their first turn, and that guide carried recorded results.** The author could not decline it and disclosed it unprompted. Measured exposure: a voided verdict naming no peer, and two notes about suite 1's instrument — no outcome class, no peer result. **The agreement is not explained by the leak, and the boundary was still breached.** The remedy is not a gate: an auto-injected operating guide must not carry recorded results. |
| **Control C external** | ✅ **YES** | RFCs, written by people who never saw this ecosystem. ⚠ Executed, never trusted: the normative fixture had a signature vector built over the wrong message for its entire life, found by **running** it. |
| **Control B** | ⛔ **NO, by construction, and it says so** | It is *our own instrument's* observation of peers. It is a **comparison set, never an answer key.** The moment it is treated as one, suite 2 is a copy of suite 1 by a slower route. |
| **"We are Kind C by construction"** | ⛔ **ASSERTED, NEVER READ** | Our position in the anchor's own taxonomy is inherited from a bring-up handoff. `VERIFICATION-ARCHITECTURE.md` is a live `unread` row in our source ledger and in the citation-debt ratchet. **The one claim about where we sit in this stack is the one nobody has checked.** `F68`'s exact shape. |

> ⭐ **Read the ledger as one sentence:** *we have three independent implementations, one and a bit
> independent instruments, two genuinely external fixtures, and an unverified claim about our own
> position.* Every other number is a count of things that share a parent.

---

## 4. Where the recursion actually stops

The operator's question was *how many layers deep does this go* — oracles on oracles. **The honest
answer is that it does not bottom out in an artifact, and pretending otherwise is the trap.**

**It stops in three places, and only three:**

1. ⭐ **Outside the ecosystem (Control C).** RFC 8032, RFC 8949. Nobody here wrote them and nobody
   here can bend them. **This is the only true terminator**, and it covers the codec and the
   signatures — a small fraction of the protocol's surface.
2. ⭐ **In a construction rather than an authority (Control A).** *Send the same input with the one
   thing under test corrected; confirm the peer answers.* This needs **no trusted third party at
   all** — it is a differential against the same peer. It is the most underrated thing in this repo
   and it scales to every probe.
3. **In a disagreement that gets adjudicated (L2 ↔ L2).** Two instruments differing is not resolved
   by a third instrument; it is resolved by the **architecture seat ruling**, which converts a
   measurement problem into an authority problem on purpose. ⛔ **Never by re-running it.** A rerun
   is what you do to a flaky measurement; two judgements differing is information.

⛔ **What is NOT a terminator, however tempting:** more peers · more runs · agreement. **Agreement
is the weakest possible signal in a stack this correlated** — it is what you get for free from
shared lineage, and the last differential was `AGREE 45 · DISAGREE 0` while the other instrument was
**blind on 44 rows.**

> **So: two or three layers deep, and the depth is not the point.** The point is that at each layer
> you can name what would falsify it. Where you cannot, you have an assertion wearing a measurement's
> clothes.

---

## 5. The moving parts — what changes under you, and how fast

**Nothing in this stack is static, and three of the four layers move without telling us.**

| Layer | Moves | Rate observed | Do we notice? |
|---|---|---|---|
| **L0** spec | constantly | **4 revisions in 6 days** (`.21→.24→.25→.26`, now `.29`) | ⛔ **No.** Nothing triggers a re-pin — the missing arrow, `WORKFLOW-SUITE-BRINGUP` §3a |
| **L1** peers | constantly | two control peers changed behaviour **inside one day**, on one git head, via uncommitted edits | ⚠ **Only by pinning content, not commits** |
| **L2** our instrument | when we change it | — | ✅ `suite_source_digest` over the bundled sources |
| **L2** their instrument | when they change it | HEAD-pinned; the check-set export is known stale | ⚠ Known, unmeasured |
| **L3** the control set | when an obligation moves | `ECP-R3`'s digest moved twice in one day | ✅ `lint-control-set` recomputes digests |

⭐ **The generalization, which is this seat's own doctrine pointed at itself:** *a commit is not a
content digest.* It has now been found at **four** levels in two days — spec version headers, the
per-peer version pin, our own instrument's `git describe`, and peer trees carrying uncommitted
edits. **Every one of them was a name standing in for content.**

⚠ **The remedy is never to chase.** Four revisions in six days cannot be tracked by a hand-authored
50-file corpus, and a seat that tries never finishes. **Pin, declare the distance, build against the
pin.** Measuring the gap is cheap; closing it is not, and the gap being *visible* is what makes a
stale measurement legible instead of silently wrong.

---

## 6. What this model says is missing

Ranked by what it costs, not by what it would take to fix.

| # | Gap | Layer |
|---|---|---|
| **1** | ⛔ **Author-context independence is enforced by nothing, and is actively breached by the harness** — the operating guide is injected before an author's first instruction, identically for every future author. A suite that agrees for shared-context reasons is worse than no suite, because it *reads* as confirmation. **The fix is ours: the injected guide must carry no recorded results** | L2 |
| **2** | ⚠ **Suite 2 reaches 3 of the 50 requirements**, so the joint denominator did not move: two instruments now measure the same 28. **What changed is that 3 of them are measured twice, by instruments sharing nothing** | L2 |
| **3** | ⛔ **No re-pin trigger and no measured distance to L0** | L0→L1 |
| **4** | ⛔ **`lint-peer-diversity` clause 2 unimplemented** — *no requirement's evidence resting on one peer or one language.* §3 is the case it would catch, and it prints that it is missing | L1 |
| **5** | ⛔ **Our own position in the taxonomy is unread** (`VERIFICATION-ARCHITECTURE.md`) | meta |
| **6** | ⚠ **Cross-peer checks fix the language of the other side** — `validate-peer`'s `origination` checks always dial Go, so a Go defect in the dialled peer scores every other implementation. **The peer pair is a parameter** and is currently a constant | L1↔L2 |
| **7** | ⚠ **3 of 50 requirements in buildable shape**, 15 of 98 obligations written at all | L2 |

---

## 7. What this document does NOT claim

- **That the layers are cleanly separated.** Keystone both *generates peers* (L1) and *runs
  instruments against them* (the census driver, L2's substrate). The generator seat does the same.
  **A tool that supplies both the subject and the harness is a real entanglement**, it is not
  written up anywhere, and it is not obviously wrong — but it is not obviously fine either.
- **That four layers is the right decomposition.** It is the one that makes the propagation rule in
  §2 come out true. A different cut might be better.
- **That anything here is ratified.** No other seat has reviewed this model. It is our reading of a
  structure we are one participant in, and the seats above us may describe it differently — in
  particular `VERIFICATION-ARCHITECTURE.md` already has a taxonomy for this and **we have not read
  it**, which is gap 5 and is the reason this section exists rather than a stronger claim.
