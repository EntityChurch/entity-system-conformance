# `spec-data/` — the pinned snapshots every requirement is authored against

**The spec is pinned, not tracked.** One directory per snapshot, each with a `MANIFEST.md` naming
the source version and a **sha256 per file**. Documents are copied in and never edited.

| Snapshot | Covers | State |
|---|---|---|
| `core-0.8.2.21` | the three core normative documents (`ENTITY-CORE-PROTOCOL` 0.8.2.21 · `ENTITY-CBOR-ENCODING` 1.6 · `ENTITY-NATIVE-TYPE-SYSTEM` 4.2.1) | **current** — the core half authors against this |
| *(extension corpus)* | `entity-system-architecture/specs/extensions/*` — 26 documents | not taken; the extension half is blocked on the `<PREFIX>-R<n>` sweep |

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
