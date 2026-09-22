# `spec-data/` — the pinned snapshots every requirement is authored against

**The spec is pinned, not tracked.** `spec-data/<spec>/v<version>/`, each version directory with a
`MANIFEST.md` naming the source version and a **sha256 per file**. Documents are copied in and never
edited.

⛔ **Everything under `spec-data/<spec>/` is VENDORED — another project's work, copied unchanged, and
not claimed by this repository.** Each specification directory carries the upstream licence files and
a `PROVENANCE.md` saying where the text comes from, under what terms, and how to verify the copy is
byte-for-byte. **We are a consumer of the specification like anyone else**; the authoritative version
is upstream, these copies are deliberately behind it, and for anything but reproducing one of our
measurements you should read upstream instead. This repository's own `LICENSE` covers the requirement
corpus, the suites and the tooling — not this directory.

| Snapshot | Covers | State |
|---|---|---|
| `entity-core-protocol/v0.8.2.26` | the three core normative documents + the encoding-vector corpus | **current** — new authoring goes here. **3 requirements** are on it |
| `entity-core-protocol/v0.8.2.25` | the same documents one revision earlier | retained; superseded within a day of being taken, and that is the normal case rather than an incident |
| `entity-core-protocol/v0.8.2.24` | the same documents | retained |
| `entity-core-protocol/v0.8.2.21` | the same six files at `0.8.2.21` / `1.6` / `4.2.1` | **retained, and still cited by 47 of the 50 requirement files.** Never deleted while a requirement names it (rule 2) |
| *(extension corpus)* | the 26 extension specifications | **not taken.** The sweep that would allocate their requirement ids (2 of 26 declare a prefix) gates **id allocation**, not authoring: an extension obligation with no id is exactly the `unallocated` shape, which is ruled shippable. The extension half is **startable**; it is unstarted because the core floor sits at 15 of 98, which is a sequencing choice rather than a block |

⚠ **47 of 50 requirements are authored against `v0.8.2.21` while the current pin is `v0.8.2.26`, and
that distance is the honest state rather than a backlog nobody noticed.** A requirement whose
section has moved is **unverified** — not wrong, not right — and re-reading it is tracked work with
a number on it. The upstream specification moved four revisions in six days; a hand-authored corpus
cannot chase that, so the rule is **pin, declare the distance, build against the pin.**

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

⚠ **Each `MANIFEST.md` also names the upstream commit its documents were copied from. That is a
convenience and never the citation.** A reader outside this ecosystem cannot resolve it — published
history is authored fresh at the release boundary, so an internal SHA points at nothing for them.
**The per-document sha256 in the same manifest is the anchor**, it is reproducible with `sha256sum`,
and a snapshot whose commit line rots is still fully verifiable through it.
