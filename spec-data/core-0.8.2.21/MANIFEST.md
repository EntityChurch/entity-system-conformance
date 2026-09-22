# SNAPSHOT `core-0.8.2.21`

**Taken:** 2026-09-11 · **Source:** `entity-core-protocol` `specs/`, at `5e259e8` (specs tree clean;
the only uncommitted file in that tree was a proposal, not a normative document).

**This is a pin, not a track.** The documents below are copied, never edited here, and never
re-synced in place. When the upstream text moves, a **new snapshot directory** is taken and the old
one stays — because a requirement authored against a section that has since moved is **unverified**,
which is neither wrong nor right, and it is the one state a mutable copy destroys.

## The documents

| File | Version header | sha256 |
|---|---|---|
| `ENTITY-CORE-PROTOCOL.md` | `0.8.2.21` | `e7551789cee136fc9549b591033527135809f9d5655fd643abccf1910b7f80e8` |
| `ENTITY-CBOR-ENCODING.md` | `1.6` | `433e094e86f0a9aa5b5d47732599b46d14fe35f3d4956371676a644c3d287f37` |
| `ENTITY-NATIVE-TYPE-SYSTEM.md` | `4.2.1` | `043fc80d4fd21ff074082e1f3c76b779d73d9f172a90d3f2a986d68e0cde740d` |

**The digest is the citable anchor, not the commit.** Published commits are authored fresh at the
release boundary (`[ADR-0012]` Am. 1), so an internal SHA resolves to nothing for a reader outside
this ecosystem. The commit above is a convenience for us; a requirement cites
`snapshot = "core-0.8.2.21"` and that name resolves to these three digests.

## What is NOT in this snapshot, and why it matters

**The extension corpus.** `entity-system-architecture/specs/extensions/*` is 26 documents and is a
separate snapshot when we get to the extension half. The core half — the `--profile core` mandatory
convergence layer — is these three documents and nothing else, which is why it can start first.

**`SPECIFICATION-FORMAT` and `GUIDE-CONFORMANCE` are not here either.** They are *authoring
standards*, not normative protocol text: we obey them, we never cite them as the source of a
requirement. A requirement's `spec` field points into this directory or it points at nothing.

## Re-taking

```bash
diff -r spec-data/core-0.8.2.21 ../entity-core-protocol/specs   # empty ⇒ upstream has not moved
```

A non-empty diff means **take a new snapshot directory**; it does not mean update this one. Every
requirement then carries the snapshot it was authored against, and re-verification is a worklist
with a count rather than a vague obligation.
