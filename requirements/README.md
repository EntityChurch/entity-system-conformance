# `requirements/` — what the protocol requires, in neutral language

**This is the deliverable.** Not a test, not code, not a description of what any oracle does. One
file per independently failable obligation, authored **from the specification** against a pinned
`spec-data/` snapshot, stating what a conformant peer does *and* what a non-conformant one does.

```
requirements/ECP-INDEX.md                        derived id↔§9-row map — scaffolding, deleted when §9 converts
requirements/<spec>/<id>.diag                    one obligation, one file (CBOR diagnostic notation, RFC 8949 §8)
requirements/entity-core-protocol/ECP-R7.diag    …so, concretely
```

⭐ **`requirements/<spec>/` mirrors `spec-data/<spec>/` name-for-name** (`ADR-0001`), so *"which
specification is this requirement from"* is answerable from the path alone. The mirror is a gate,
not a convention: `tools/requirement-gate.py` fails the build if a file's directory and its
`snapshot` field name different specs. **This directory was called `core` until 2026-09-15** — an
abbreviation this seat invented, which collided with *core profile*, a real and different thing, and
which no instrument in the tree could see was wrong.

## The id, and its three states

The core spec's prefix is **`ECP`** and the allocation is fixed at `ECP-R1`…`ECP-R98` in §9 document
order, *before* the conversion lands, so we are not blocked
(`PROPOSAL-THE-CORE-TIER-HAS-98-OBLIGATIONS-AND-NOT-ONE-OF-THEM-HAS-A-NAME` §2). Every requirement
declares `id_status`, and **all three states are real and countable**:

| `id_status` | Means | Filename |
|---|---|---|
| `allocated` | binds a §9 row's own id | `ECP-R66.diag` |
| `pending-split` | the §9 row it belongs to **bundles**; this obligation is the 2nd or 3rd under one id, and arch appends its number from `ECP-R99` — **the split is routed, never performed here** | `ECP-R66-pending-b.diag` |
| `unallocated` | ⭐ **a binding MUST in the specification body with NO §9 row at all.** Not a bundled row — an absent one | `UNALLOCATED-<slug>.diag` |

> ⭐ **`unallocated` is the state nobody expected, and it is now a sanctioned measurement: the
> FLOOR-GAP WORKLIST.** Ruled 2026-09-12 (`CQ-9`): §9 is the membership authority for **the floor**
> and never was an enumeration of the protocol's obligations — **418 `MUST` tokens in §1–§8 against
> 66 floor rows.** So a body MUST binds whether or not §9 lists it, `ECP-R<n>` keys §9 rows, and a
> non-zero `unallocated` count reads ***"the floor is missing a row"***, never *"the ids do not
> reach"*. **Ship it and count it** — `make lint` prints the figure every run.

**Discharging one `unallocated` row** — the procedure, not a judgement call: *is this obligation
cross-peer observable, and does a peer violating it fail to interoperate?*

- **yes** → it belongs on the floor. A §9 row is a normative change and takes a proposal (L1, and
  **not ours to write**); the row is added, `ECP` extends **by append**, the file becomes
  `allocated`.
- **no** → it binds, it is testable, and it is **not floor**. The check measures it and **declares
  it non-floor**, so a peer failing it does not read as failing conformance.

⚠ **And the count is a floor on the gap, never a ceiling.** Batch 1 filed three; arch's own reading
of §4.5 **and §4.5a** found **six**. We reached the obligations our reference checks pointed at and
stopped — `AP-2`. **A batch's unit is a specification SECTION, not a check category.**

**We never mint an id in arch's namespace.** `pending-split` and `unallocated` files carry no
`ECP-R<n>` of their own; they name the row they belong under, or none.

## What every file carries

The id + status · the spec sections · **the snapshot** · the level **and its basis** (`level_basis`:
`keyword`, the default, or `entailed` — a level we ARGUED because no keyword states it; counted every
run, added 2026-09-12) · a `reading` that quotes the
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
