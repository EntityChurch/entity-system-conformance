# PROVENANCE — this directory is someone else's work, vendored unchanged

**The documents under `v<version>/` are copies of the Entity Core Protocol specification, taken
from the `entity-core-protocol` project. They are not authored here, not maintained here, and
nothing in this repository claims them.**

We are a **consumer of this specification, like anyone else.** This repository builds an
independent conformance instrument *against* the protocol; to do that honestly, every requirement
we write has to name the exact text it was read from, so the text is copied in and pinned. That is
the whole reason these files exist here.

## What is vendored, and under what terms

The upstream project licenses its own work in two parts, and both files are copied beside this one,
unmodified:

| File | Covers |
|---|---|
| `LICENSE` | **CC BY-ND 4.0** — the specification **prose**: `ENTITY-CORE-PROTOCOL.md`, `ENTITY-CBOR-ENCODING.md`, `ENTITY-NATIVE-TYPE-SYSTEM.md` |
| `LICENSE-CODE` | **Apache-2.0** — the machine-readable files, which upstream states are "functionally code": the `test-vectors/` corpus |
| `NOTICE` | the upstream attribution notice |

⭐ **The no-derivatives term is not a constraint we work around — it is the same rule this
directory already ran under.** `spec-data/README.md` rule 1: *never edit a document inside a
snapshot; if upstream moved, take a new directory.* **Every file here is byte-for-byte upstream**,
and each version directory's `MANIFEST.md` carries a **sha256 per document** so anyone can confirm
that without trusting us:

```
sha256sum -c   # against the digests in v<version>/MANIFEST.md
```

**If you want to change the specification, take it upstream** — that project runs a proposal
process, and this repository has a standing prohibition against authoring the specification. Where
we think the text is wrong or ambiguous, we route a finding to its authors and record the question;
we never publish an amended version.

## Where the real thing lives

The authoritative, current specification is the upstream `entity-core-protocol` project. **These
snapshots are deliberately behind it** — a pin, not a track — and the distance is stated in
`spec-data/README.md` rather than hidden. **For anything except reproducing one of our
measurements, read upstream, not here.**

`LICENSE` at the root of this repository (Apache-2.0) covers **our** work: the requirement corpus,
the suites and the tooling. It does not extend to this directory, and this directory's terms do not
extend to ours.
