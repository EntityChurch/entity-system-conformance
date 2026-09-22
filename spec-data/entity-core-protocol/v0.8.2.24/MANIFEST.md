# SNAPSHOT `core-0.8.2.24`

**Taken:** 2026-09-14 · **Source:** `entity-core-protocol` `specs/`, at `cca71391` (specs tree clean).

**This is a pin, not a track.** The documents below are copied, never edited here, and never
re-synced in place. `core-0.8.2.21` stays — a requirement authored against it remains readable and
re-verifiable, which is the whole reason the old directory is never deleted (`spec-data/README.md`
rule 2).

## The documents

| File | Version header | sha256 |
|---|---|---|
| `ENTITY-CORE-PROTOCOL.md` | `0.8.2.24` | `827edf9b01e48301ea3fcc2d2365d9270cc85063dcbe49f0dba4c8d861cee0e9` |
| `ENTITY-CBOR-ENCODING.md` | `1.7` | `dd6aa47de343b335ececc3c7c654da019dc9e473eb4639af3dc9d7a202a8393f` |
| `ENTITY-NATIVE-TYPE-SYSTEM.md` | `4.2.1` | `043fc80d4fd21ff074082e1f3c76b779d73d9f172a90d3f2a986d68e0cde740d` |
| `test-vectors/ecf-conformance/conformance-vectors.cbor` | — **normative** (`ENTITY-CBOR-ENCODING` App. E) | `9695b1f1d939cfdfdd4297f8ad32122d424b1ec180cfae74c92d509d88f7c6dc` |
| `test-vectors/ecf-conformance/conformance-vectors.diag` | — non-normative source of the above | `da521d67aa8193a3bf9acd232088d8515d50333f0294c65a5df3b45f46a1a87b` |
| `test-vectors/ecf-conformance/CHANGELOG.md` | — corpus history | `47f24274185fde6a34834f0f1ac895cfa50d2c74c9c8f16b9eaac24268475261` |

## What moved from `core-0.8.2.21`, measured

**Two of the six pinned files moved. Four are byte-identical to the previous snapshot**, and saying
so is the point of taking a digest per file rather than per snapshot:

| File | vs `core-0.8.2.21` |
|---|---|
| `ENTITY-CORE-PROTOCOL.md` | `0.8.2.21` → `0.8.2.24` — **three revisions folded** (.22 and .23 on 2026-09-13, .24 on 2026-09-14) |
| `ENTITY-CBOR-ENCODING.md` | `1.6` → `1.7` — §5.4 item 1 only |
| `ENTITY-NATIVE-TYPE-SYSTEM.md` | **unchanged** (identical sha256) |
| all three ECF corpus files | **unchanged** (identical sha256) — suite 1's 71 corpus vectors carry over untouched |

**Changed sections, by line count** (`ENTITY-CORE-PROTOCOL`): §5.2 (53) · §6.3 (37) · §5.4 (23) ·
§5.5 (11) · §5.6 (10) · §5.2a (9) · §6.8 (9) · §1.8, §3.1, §3.3, §3.6 (1 each).
`ENTITY-CBOR-ENCODING`: §5.4 (2).

### ⭐ §9 is BYTE-IDENTICAL across the three revisions

Verified whole, not sampled: §9 through end-of-document is the same 37,645 bytes in both snapshots.

**Two consequences, and the second is a finding.**

1. **No `ECP` id moves.** The `ECP-R1`…`ECP-R98` allocation is positional over §9 document order, so a
   §9 edit would have shifted every id after the insertion point. It did not. `requirements/ECP-INDEX.md`
   needs no rework and `tools/ecp-index.py --check` reproduces unchanged.
2. **The body gained a security-critical `[MUST]` cluster and the floor did not follow.** .23 closes a
   **capability forgery** — every authority lookup in §5.2/§5.5/§5.5a resolved an entity by a
   wire-supplied address nothing verified — and states **resolution integrity** as a new §1.8 `[MUST]`
   with two conformant mechanisms, makes §3.1's `included` keying normative in both directions, adds
   three §5.2a dispositions, and pins the handler frame in §6.3/§6.8. **None of it has a §9 row.**
   That is `F4`'s shape with fresh evidence, and under `CQ-9`'s ruling every one of these authors as
   `unallocated` — the floor-gap worklist, which is exactly what the count is for.

### Quote survival: 50 of 50 requirement files clean

Every normative sentence quoted in `requirements/core/*.toml` still appears **verbatim** in this
snapshot. The three revisions are **additive** — new clauses, new table rows, moods corrected from
indicative to `[MUST]` — not rewrites of the text our readings argue from. So no requirement's
argument was invalidated by the bump; what the additions do is **add obligations and pin codes that
were previously unpinned**, which is a re-read worklist, not a repair worklist.
