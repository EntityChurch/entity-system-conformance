# STATUS — entity-system-conformance

**The rolling status of the instrument.** One file, kept current, written for someone deciding
whether to rely on it. **Every number here is measured, and the ones that flatter us are marked.**

*Current as of 2026-09-17.*

---

## The one-paragraph state

The requirement corpus exists and is real: **50 obligations authored from pinned specification
text**, each independently failable, each with a negative control. **Two independent suites** run
against real peers — one Python, one Rust, sharing no code, no codec, no cryptography and no
language — and the second was built by an author who had not read the first. **28 of the 50
requirements have been executed against real peers; 22 have not.** Against the protocol's core
floor of 98 obligations, **15 are covered.** This is an early instrument that is honest about its
own coverage, not a finished one.

## The numbers

| | | |
|---|---|---|
| Requirements authored | **50** | 15 bind a floor row · 8 await a floor-row split upstream · 27 bind a body obligation the floor does not list |
| Core floor covered | **15 of 98** | the rest is authoring not yet done |
| Executed against real peers | **28 of 50** | ratcheted down-only. A requirement nobody has run has not been shown to measure anything |
| Obligation separated from probe | **3 of 50** | the rest still fuse the two in one file; converting is per-file because a conversion that surfaces a second obligation is a finding, and a bulk pass cannot file one |
| Suites | **2** | `py-prototype` reaches 28 requirements, `rs-conformance` reaches 3 |
| Measured by **both** suites | **3** | where the joint coverage is genuinely two instruments deep |
| Checks re-read against the obligation they measure | **6 of 31** | the other 25 are not claimed wrong — nothing has established which version of the rule they implement |
| Spec snapshot pinned | `v0.8.2.26` | upstream is ahead; 47 of 50 requirements are authored against the older `v0.8.2.21` |
| Peers driven | **40 declared** | ⚠ **three lineages, not forty** — see below |

**Four down-only ratchets are printed on every run** and each names something *not* established:
requirements no suite has executed · requirements whose obligation and probe are still fused ·
material relied on but unread · checks never re-read against their obligation. **They are lowered
by doing the work, never by editing the number.**

## What is deliberately not claimed

- ⚠ **A peer count is not an independence count.** The 40 declared peers are 36 from one generated
  cohort, 3 composed by one tool, and 1 reference implementation — **three lineages.** A defect in
  a generator is dozens of correlated failures that read as dozens of confirmations. *Running more
  peers is more evidence at the layer where evidence is already cheap.*
- ⚠ **Agreement between two suites is the weakest signal here, not the strongest.** It is what
  shared lineage gives you for free. The disagreements are the product.
- ⛔ **Author independence between suites is not enforced by anything.** Language, dependency and
  codec independence are gated and have fired. Context independence is not, and is currently
  breached by the agent harness that injects this repo's operating guide before an author's first
  instruction. Measured exposure for suite 2 was small and is written up; the boundary was still
  breached, and the remedy — an injected guide that carries no recorded results — is ours.
- ⛔ **A verdict is only evidence with the digest of the obligation it scored.** One requirement's
  text moved twice in a single day, and three peers' recorded passes were against text that no
  longer existed. Every verdict now pins that digest.
- **Coverage of the extension corpus: none.** 26 extension specifications, no snapshot taken. Not
  blocked — sequenced behind the core floor.

## Recent movement

**A second suite exists, and the agreement was the least interesting thing it produced.**
`rs-conformance` — Rust, `std` only, zero dependencies, with SHA-256 and canonical CBOR written
from the published standards rather than taken from a library — was built from the brief, the
pinned spec text and three obligation files, by an author who read neither the first suite's source
nor its recorded results. On its first comparison the two suites agreed on both comparable rows
**and agreed on the outcome class, not merely the verdict** — two failures that the specification
requires to be scored separately because their remedies are opposite. A suite that collapsed them
would score every top-line verdict correctly and still be wrong.

**And it immediately found a defect in the requirement it was handed.** Its author opened the
snapshot that requirement itself declares, in a section that requirement itself cites, and found
the response code the requirement said was unassigned. Three review passes and a green gate suite
had missed it. The suite did not quietly re-score: it scored the shared obligation and emitted the
disputed part as a contested block keyed to the requirement id — which is the intended behaviour,
arriving from the direction that tests it.

**Seven gate defects surfaced in the same pass**, four reported by an author who edited no gate.
Gates written against one hand-written Python suite mis-fired the moment a compiled suite appeared:
one refused the author's declaration of what they had *not* read, one flagged a compiler's
generated output, and one applied a per-suite row floor that let a deliberately small second suite
drag the first below it. **No amount of reasoning about one suite would have found any of them.**

## Open, in priority order

1. **Strip recorded results out of the auto-injected operating guide** — the author-independence
   remedy, and it is not a gate.
2. **Re-author the contested requirement against the current snapshot and re-measure it** on the
   peers that scored it.
3. **One requirement was measured before the handshake** rather than on an established connection
   as its own text states — re-run in the stated position.
4. **No verdict exists for *observed but not scoreable*.** One requirement emits a skip instead,
   and a skip counts as a failure — so the instrument currently misreports a case the
   specification explicitly says must not be asserted on.
5. **The generated peer cohort is mostly unrun** by the second suite.
6. **Nothing triggers a re-pin when the specification moves.** Every artifact here is pinned to the
   one above it and none is pinned to the top.
7. **Twelve requirements unblocked by a recent ruling** are authored but not yet executed.

## How to check any of this

`make check` runs the gates and prints every ratchet. `make differential` joins the instruments by
requirement id and lists every check the reference oracle ran for which this repo has no
requirement at all — that list, not the agreement, is the next batch's worklist. `docs/CLI.md` has
the rest.
