# SNAPSHOT `entity-core-protocol/v0.8.2.26`

**Taken:** 2026-09-16 · **Source:** `entity-core-protocol` `specs/`, at `b823262` (specs tree clean).

**This is a pin, not a track.** The documents below are copied, never edited here, and never re-synced
in place. `v0.8.2.25`, `v0.8.2.24` and `v0.8.2.21` stay — a requirement authored against any of them
remains readable and re-verifiable, which is why an old directory is never deleted
(`spec-data/README.md` rule 2).

**Why it was taken:** the signature-message ruling. `§7.3` is declared the single normative home of
*what a signature signs* — **the full `content_hash`, format code ‖ digest** — which unblocks the
twelve `multisig` requirements parked since 2026-09-12, and settles our `CQ-45`: **§4.11's cause table
assigns CODES and does not define the CLASS**, so the frame obligation reaches the root-entity-hash
refusal even though `CQ-37` left its `(status, code)` alone. A requirement authored against `.25`
cannot express either.

## The documents

| File | Version header | sha256 |
|---|---|---|
| `ENTITY-CORE-PROTOCOL.md` | `0.8.2.26` | `741294e3a01fd738898968a5827c416805baad830338117f7dd24005a96b6feb` |
| `ENTITY-CBOR-ENCODING.md` | `1.7` ⚠ | `8bcc6fdbf1e260737fbd2de4c862c38418be17eade255e08da2b186be1b68fe4` |
| `ENTITY-NATIVE-TYPE-SYSTEM.md` | `4.2.1` ⚠ | `cb0a63e23862dccb6c421fabbcdcce765a67a8fb8f818b1a1eb41f1530460305` |
| `test-vectors/ecf-conformance/conformance-vectors.cbor` | — **normative** (`ENTITY-CBOR-ENCODING` App. E) | `9695b1f1d939cfdfdd4297f8ad32122d424b1ec180cfae74c92d509d88f7c6dc` |

## ⚠ TWO DOCUMENTS CHANGED NORMATIVE CONTENT WITHOUT CHANGING THEIR VERSION NUMBER (`F79`)

**`ENTITY-CBOR-ENCODING` is `1.7` at `.25` and `1.7` here. `ENTITY-NATIVE-TYPE-SYSTEM` is `4.2.1` at
both.** Their bytes are not the same:

| document | `.25` sha256 | `.26` sha256 |
|---|---|---|
| `ENTITY-CBOR-ENCODING.md` | `dd6aa47de343b335…` | `8bcc6fdbf1e26073…` |
| `ENTITY-NATIVE-TYPE-SYSTEM.md` | `043fc80d4fd21ff0…` | `cb0a63e23862dccb…` |

Both edits are substantive. Appendix E's `signature` category was **redefined** — it read *"signs the
canonical bytes"* and now reads *"signs the entity's `content_hash` … and **not** the ECF bytes"*, plus
a new `[MUST]` requiring a cross-check vector. §10.2's sentence changed from *"the content hash
**digest** bytes"* to *"the **full** `content_hash` — format code ‖ digest"*.

⛔ **A CONSUMER PINNING BY VERSION STRING WOULD SEE NOTHING MOVE, AND WOULD BE WRONG ABOUT A `[MUST]`.**

⭐ **This is why this file pins a sha256 per document and not a version**, and it is a caveat we owe
against our own advice: on **2026-09-16 we told `entity-core-keystone`** (`ROUTING-2026-09-16-a-…`) to
record a per-peer `spec_pin` as *"the spec version string … in the ecosystem's own form"*. **That
answer is still right for their question** — a peer is swept to a protocol revision and
`ENTITY-CORE-PROTOCOL` *did* bump — **but the general claim underneath it is not: a version string is
not a content digest, and this snapshot is the counterexample, taken the same day.** Carried to them
as a caveat rather than a retraction; recorded on `TRACKER-entity-system-architecture.md` as `F79`,
because the version-hygiene question is arch's.

⇒ **ROUTED 2026-09-16 (b)** as
`ROUTING-2026-09-16-b-entity-system-architecture-the-version-header-is-declared-the-source-of-truth-and-two-documents-falsified-it.md`
(`CQ-46`/`CQ-47`/`CQ-48`), and **the ask changed shape on contact with their tree.** Arch already run
a proposal-first rule and an L1 gate (`entity-system-arch-tools/spec-tool/provenance.py`), and **had
already measured and rejected keying it on the version header** — *"both changed zero version headers,
**correctly** … a version-triggered gate is silent on precisely the class arch uses most."* So the
packet does **not** ask for the bump. It asks **what a downstream consumer pins**, given that on this
boundary the version header did not move **and the corpus did not either** — and it carries `CQ-47`,
where `ENTITY-NATIVE-TYPE-SYSTEM`'s §10.2 edit fires **neither** of that gate's two triggers.

⚠ **The fixture is unchanged and is NOT currently blessed on one category.**
`conformance-vectors.cbor` is byte-identical to the `.25` pin (`9695b1f1…`) and arch state its three
`signature.*` vectors are **under correction** — the recompute is routed to `entity-core-go`, and the
cross-bless with our independent codec is routed to **us**. **The other 68 vectors are unaffected.**
`make test` runs all 71; until the new fixture lands, a conformance number of ours citing this corpus
must say the `signature` category is under correction.
