# `requirements/` — what the protocol requires, in neutral language

**This is the deliverable.** Not a test, not code, not a description of what any oracle does. One
file per independently failable obligation, authored **from the specification** against a pinned
`spec-data/` snapshot, stating what a conformant peer does *and* what a non-conformant one does.

```
requirements/ECP-INDEX.md        derived id↔§9-row map — scaffolding, deleted when §9 converts
requirements/core/<id>.toml      one obligation, one file
```

## The id, and its three states

The core spec's prefix is **`ECP`** and the allocation is fixed at `ECP-R1`…`ECP-R98` in §9 document
order, *before* the conversion lands, so we are not blocked
(`PROPOSAL-THE-CORE-TIER-HAS-98-OBLIGATIONS-AND-NOT-ONE-OF-THEM-HAS-A-NAME` §2). Every requirement
declares `id_status`, and **all three states are real and countable**:

| `id_status` | Means | Filename |
|---|---|---|
| `allocated` | binds a §9 row's own id | `ECP-R66.toml` |
| `pending-split` | the §9 row it belongs to **bundles**; this obligation is the 2nd or 3rd under one id, and arch appends its number from `ECP-R99` — **the split is routed, never performed here** | `ECP-R66-pending-b.toml` |
| `unallocated` | ⭐ **a binding MUST in the specification body with NO §9 row at all.** Not a bundled row — an absent one | `UNALLOCATED-<slug>.toml` |

> **`unallocated` is the state nobody expected, and its count is a measurement worth having.** §9.1 is
> introduced as *"the universal MUST-implement floor"*. If a MUST in the body has no §9 row, then
> either §9 is a summary rather than an inventory, or the floor has a hole — and **those have
> opposite consequences for what a conformant peer must do.** Routed to arch; see
> `docs/status/FINDINGS-FROM-AUTHORING.md`.

**We never mint an id in arch's namespace.** `pending-split` and `unallocated` files carry no
`ECP-R<n>` of their own; they name the row they belong under, or none.

## What every file carries

The id + status · the spec sections · **the snapshot** · the level · a `reading` that quotes the
normative text and **argues the interpretation** · the observable surface · **preconditions as
data** · and **both arms plus a negative control**.

Four rules, each earned rather than assumed:

1. **One independently failable obligation per file.** A conversion that produces two is a
   **finding to route**, not a quiet split.
2. **Every requirement has a negative control** — especially the ones that cannot fire against a
   correct implementation. *A check that cannot be made to fail has not been shown to measure
   anything.*
3. **Assert the code, not just the status**, and assert the **decoded field**, never a substring
   (`GUIDE-CONFORMANCE` §5.2b.1).
4. **`reading` argues; it does not restate.** It is where the next person finds out *why* it was
   read this way, and it is the first thing arch opens when a suite disagrees with the oracle.

## `oracle_check` is provenance and never authority

Where a file names a reference-oracle check, that is a **cross-reference for the differential run**.
It is never the source of the requirement and never the source of an expected value. If a line in
`reading` is justified only by what the oracle does, the requirement was transcribed and is wrong.

Some files carry `[requirement.predicted_disagreement]` — **a falsifiable prediction, recorded
before any suite exists**, that our reading of the spec and the reference oracle's check will
disagree. It is not a finding: it is a bet with a date on it, and the first differential run settles
it. A prediction that turns out wrong is as informative as one that turns out right, and much more
informative than one never written down.
