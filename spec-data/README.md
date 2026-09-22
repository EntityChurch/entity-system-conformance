# `spec-data/` — the pinned snapshots every requirement is authored against

**The spec is pinned, not tracked.** `spec-data/<spec>/v<version>/`, each version directory with a
`MANIFEST.md` naming the source version and a **sha256 per file**. Documents are copied in and never
edited.

| Snapshot | Covers | State |
|---|---|---|
| `entity-core-protocol/v0.8.2.24` | the three core normative documents (`ENTITY-CORE-PROTOCOL` 0.8.2.24 · `ENTITY-CBOR-ENCODING` 1.7 · `ENTITY-NATIVE-TYPE-SYSTEM` 4.2.1) + the ECF corpus | **current** — new authoring goes here |
| `entity-core-protocol/v0.8.2.21` | the same six files at `0.8.2.21` / `1.6` / `4.2.1` | **retained, and still cited by most of `requirements/`.** Never deleted while a requirement names it (rule 2) |
| *(extension corpus)* | `entity-system-architecture/specs/extensions/*` — 26 documents | not taken. ⛔ **The old note here said "blocked on the `<PREFIX>-R<n>` sweep." That is STALE — see `F66`.** The sweep (2 of 26 declare a prefix) gates **id allocation**, not authoring: an extension obligation with no prefix is exactly `unallocated`'s shape, ruled shippable 2026-09-12 (`CQ-9`). The extension half is **startable**; it is unstarted because the core floor is at 15 of 98, not because anything blocks it |

## Naming, and what a snapshot directory is a snapshot OF

⭐ **`spec-data/<spec>/v<version>/` — the directory is named after the SPEC REPOSITORY OR DOCUMENT it
holds, lowercased, never an abbreviation** (`ADR-0001`). The top level is the specification that
declares the obligations — not the repo that consumes it, not the run. Version directories sit
inside it, which is `entity-core-keystone`'s convention (`protocol-generator/shared/spec-data/v…/`),
and it means a 27th extension adds one directory rather than one per version.

> ⛔ **This replaced `core-<version>` on 2026-09-15, and the old name is worth remembering because
> nothing could see what was wrong with it.** `core` was an abbreviation **this seat invented**, and
> it collided head-on with **core profile** — a real and different thing used constantly
> (`--profile core`, 16 core-profile categories, 201 core-profile declarations). So
> `requirements/core/` read as *core-profile requirements* and meant *core-protocol requirements*.
> It survived four working sessions and a green `make check` every time. **A gate cannot see a
> name.** The mirror between `requirements/<spec>/` and `spec-data/<spec>/` is now enforced by
> `tools/requirement-gate.py`, which is the only part of this a reader does not have to remember.

`entity-core-protocol/v0.8.2.24` pins the three core normative documents in one directory because
they version together and a core requirement cites across all three; `MANIFEST.md` stays
authoritative for the per-document versions, which the directory name deliberately does not carry.
An extension pins separately (`extension-content/v3.7/`, `extension-tree/v4.11/`) because it versions
on its own cadence and a peer implements an arbitrary subset.

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
3. **Every requirement carries `snapshot = "<spec>/v<version>"`.** A requirement without one cannot
   be re-verified, because nobody can tell which text it was read from. **And it must live in
   `requirements/<spec>/`, matching the first component** — the two trees mirror name-for-name, and
   `tools/requirement-gate.py` fails the build if a file's path and its `snapshot` disagree about
   which spec it states.
4. **The digest is the citation**, not the commit — `[ADR-0012]` Am. 1.
