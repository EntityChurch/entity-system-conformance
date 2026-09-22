# entity-system-conformance

**The independent conformance instrument for the Entity Core Protocol** — a neutral,
language-agnostic statement of what the protocol requires, and **as many independently built test
suites over it as we care to build.**

This repo exists to answer one question that nothing else in the ecosystem can:

> **Is the peer wrong, or is the oracle wrong?**

A single oracle cannot tell you. Every check it runs is scored by the same judgement that wrote the
check, so its own errors are invisible **by construction** — and a bug in the oracle does not stay a
bug in the oracle. It gets enforced into every peer that passes, and then it is indistinguishable
from the protocol. **The thing we are protecting against is canonicalizing one implementation's bugs
as the standard.**

---

## The shape

```
requirements/   ← THE DELIVERABLE. What the protocol requires, in neutral language,
                  keyed to <PREFIX>-R<n> requirement ids. Not code, not a test.
suites/         ← N independent implementations of those requirements. Different
                  languages, different authors, built to disagree with each other.
substrate/      ← peers we CONSUME to run suites against. We never write one.
spec-data/      ← the pinned spec snapshot each requirement was authored against.
```

**`requirements/` and `suites/` being separate directories is the whole design.** One neutral
statement, many implementations of it. That is the same pattern that worked twice already in this
ecosystem — one protocol, many generated peers; one extension spec, many language implementations —
and the reason to expect it to work a third time is that it is the *same* pattern, not an analogy to
it.

**The convergence is the point, and it is measurable.** The first suite will disagree with the
reference oracle in places where the neutral requirement was ambiguous. Those disagreements are the
product: each one is either a specification gap, an implementation bug, or a bad check, and finding
out which is what refines the requirement. Run that loop enough times and the requirements stop
producing disagreements — at which point a sixth suite is not worth building, and we will know that
rather than assume it.

## What this repo never does

- **It never ships a peer.** The moment it does, it is writing its own exam and the reason for its
  existence collapses. A behaviour no available peer provides is a **finding**, not a build task.
- **It never authors the specification.** It reads the spec and states what it requires. Where the
  spec is unclear, that is a finding routed upstream — not a decision made here.
- **It is not the only scorer.** The existing reference oracle stays, permanently. Two instruments
  are worth their cost only if both run and disagreements get adjudicated by a third party.

## Where to start

**`docs/STATUS.md` lists the four documents to read, in order.** Short version:

| | |
|---|---|
| `AGENTS.md` | the charter, the three prohibitions, the bring-up sequence |
| `docs/status/EXPORT-2026-09-11-…` | the reference check set **measured** — this is the worklist |
| `docs/DESIGN-THE-REQUIREMENT-FORMAT.md` | how a requirement is written |
| `docs/DESIGN-THE-SUITE-CONTRACT.md` | how a suite is invoked and what it emits |
| `docs/OPEN-QUESTIONS.md` | what is unsettled, and who owns each |

**The two design documents are first cuts written by the architecture seat before this repo had an
agent. They are meant to be argued with.** A format that survives first contact with real
requirements unchanged was probably transcribed rather than designed.

## Status

**Bootstrap. Nothing is built.** The first concrete slice is seven core-profile categories that are
fully resolved and blocked on nobody — 55 checks — and it can start today.

