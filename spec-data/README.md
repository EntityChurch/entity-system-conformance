# `spec-data/` — the pinned snapshots every requirement is authored against

**The spec is pinned, not tracked.** One directory per snapshot, each with a `MANIFEST.md` naming
the source version and a **sha256 per file**. Documents are copied in and never edited.

| Snapshot | Covers | State |
|---|---|---|
| `core-0.8.2.24` | the three core normative documents (`ENTITY-CORE-PROTOCOL` 0.8.2.24 · `ENTITY-CBOR-ENCODING` 1.7 · `ENTITY-NATIVE-TYPE-SYSTEM` 4.2.1) + the ECF corpus | **current** — new authoring goes here |
| `core-0.8.2.21` | the same six files at `0.8.2.21` / `1.6` / `4.2.1` | **retained, and still cited by most of `requirements/`.** Never deleted while a requirement names it (rule 2) |
| *(extension corpus)* | `entity-system-architecture/specs/extensions/*` — 26 documents | not taken. ⛔ **The old note here said "blocked on the `<PREFIX>-R<n>` sweep." That is STALE — see `F66`.** The sweep (2 of 26 declare a prefix) gates **id allocation**, not authoring: an extension obligation with no prefix is exactly `unallocated`'s shape, ruled shippable 2026-09-12 (`CQ-9`). The extension half is **startable**; it is unstarted because the core floor is at 15 of 98, not because anything blocks it |

## Naming, and what a snapshot directory is a snapshot OF

`<area>-<version>` — **one directory per document set per version**, where the *area* is the
specification that declares the obligations, not the repo and not the run. `core-0.8.2.24` pins the
three core normative documents because they version together and a core requirement cites across all
three. An extension pins separately (`ext-content-<v>`, `ext-network-<v>`) because it versions on its
own cadence and a peer implements an arbitrary subset.

> ⛔ **A run therefore has a snapshot SET, never a snapshot.** A peer under test implements core at one
> version plus N extensions at N versions, and the requirements selected for a run may legitimately
> cite more than one snapshot — including two versions of the same area, mid-re-base. **A verdict
> document that reports a single scalar `spec.snapshot` is misreporting what it measured** (`F65`,
> `AP-13`). The set is **derived from the requirement files actually selected**, never asserted by
> the runner.

## Why a snapshot rather than a submodule or a path

**A check is a claim about what a spec section requires.** When the section moves, the check is
**unverified** — not wrong, not right, *unverified* — and that is a state a live path cannot
represent. A tracked checkout silently re-points every citation in the tree at text nobody has
re-read; a snapshot makes the re-read a worklist with a number on it.

This is the same contract `entity-core-keystone` runs
(`protocol-generator/shared/spec-data/` + `tools/keystone-spec-pin.env`) and the same one the
generation seat runs (`snapshot = "content-v3.7"` in every check). We are not inventing it, and the
field name is theirs on purpose.

## Rules

1. **Never edit a document inside a snapshot.** If upstream moved, take a new directory.
2. **Never delete a snapshot** while any requirement cites it. A retired snapshot is how a
   superseded requirement stays readable.
3. **Every requirement carries `snapshot = "<dir name>"`.** A requirement without one cannot be
   re-verified, because nobody can tell which text it was read from.
4. **The digest is the citation**, not the commit — `[ADR-0012]` Am. 1.
