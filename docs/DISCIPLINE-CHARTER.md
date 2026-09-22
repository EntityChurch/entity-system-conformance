# DISCIPLINE CHARTER — `entity-system-conformance`

**This repository's own disciplines, D13 onward.** D1–D12 are the ecosystem's and are not restated
here. A discipline is added only on its **second** incident in a different shape, and only with an
enforcement point someone can run — this file carries the rule, the trigger, and the enforcement.
**`docs/PROCESS.md` explains the ladder these sit on.**

**Load by trigger, not all at once.** Open this file when its trigger fires.

> **Note for a reader outside this project.** `AP-<n>` and `F<n>` are stable ids for incidents and
> findings, and the incident write-ups themselves are internal working documents — a rule here is
> meant to stand on the sentence that states it, not on a citation you have to follow. **If a rule
> below is only intelligible by opening something you cannot see, that is a defect in the rule.**

---

## D13 — scope is set by what the specification declares normative, never by a pointer into it

**Trigger:** starting a requirement batch · taking or amending a `spec-data/` snapshot · any "we have
read / pinned / covered X" claim.

> **The reference check set, a citation, a document list, or a section a finding points at selects
> where to START. The specification's own statements of scope — a section headed normative, a
> sub-section below the one cited, an artifact a document declares to be its conformance contract —
> decide where to STOP.**

**Why it is a discipline and not advice:** it bit twice, in two shapes, and both gaps were exactly the
surface this seat exists to find. `AP-2` (batch 1): three of six floor holes missed because we read
the clauses the checks exercised. `AP-2`, second instance (batch 3): the ECF conformance fixture
omitted from the snapshot because we pinned a document list.

**Enforcement:**

| Shape | Enforcement point | Kind |
|---|---|---|
| a batch reads what the checks cite | each batch's findings entry records **the section range read** and a disposition for every normative clause in it that was **not** authored | procedural, reviewed at the batch's close |
| a snapshot pins what a list names | `tools/spec-snapshot-gate.py` — any pinned document naming a directory-qualified artifact path (`.cbor .diag .json .jsonl .toml`) the snapshot does not pin is a **finding**; self-tested with the control isolated, and executed against the real pre-fix snapshot | mechanical, in `make lint` |

**Not yet enforced, and said so:** a pinned document naming a *normative document* outside the snapshot
(`SDK-OPERATIONS.md`, `EXTENSION-TREE.md`) is deliberately out of the core snapshot's scope today
(`MANIFEST.md` states why). The rule above is scoped to artifacts because that is the case that bit;
widening it to documents without an incident would be a rule stated over cases its author imagined
(`AP-3`).

---

## D14 — a requirement is not landed until a suite has run it against real peers

**Trigger:** authoring or reviewing a requirement · calling a category "done", "authored" or "covered" · planning
the next batch.

> **An artifact whose job is to be executed is evidence only once it has been executed.** A requirement file, a
> vector, an arm, a negative control — reading, reviewing and schema-gating it establishes that it is well-formed,
> never that it measures anything. **The loop closes per category: author, implement, run on Keystone, generator and
> core-go peers, compare against the reference oracle on the same peers and posture, triage — before the next
> category is authored.**

**Why it is a discipline and not advice:** it bit twice, in two shapes. `AP-7` (batch 3): a pinned vector corpus read
by its descriptions, never executed — one execution in batch 4 surfaced `F30`. `AP-9` (2026-09-13, operator audit):
50 requirement files authored, reviewed and gated and **0 run**; the first run found `F40` (an arm narrower than its
own obligation), an undeclared oracle-profile input, and two undocumented contracts in the driver we plug into — none
reachable by reading.

**Enforcement:**

| Shape | Enforcement point | Kind |
|---|---|---|
| requirements accumulate faster than any suite runs them | `tools/requirement-gate.py` — counts files implemented by no suite (`suites/*/IMPLEMENTS`) and **fails if the count exceeds `requirements/UNEXECUTED-CEILING`**, which only ever goes down; a manifest naming a missing file is refused. Self-tested (3 planted defects) | mechanical, in `make lint` |
| a suite's claimed coverage drifts from what it runs | `suites/py-prototype/tests/test_manifest.py` — `IMPLEMENTS` must equal the `CHECKS` table; `make build` writes each listed file's sha256 into the bundle's `BUILD.json`, so every verdict names the requirement text it measured | mechanical, in `make test` |
| a codec defect reaches a peer as a FAIL | `suites/py-prototype/tests/test_corpus.py` — the snapshot's ECF corpus from its `.cbor` artifact (digest checked), every vector run or declared not-run with a reason, accounting asserted (71/71 run); `tests/test_ed25519.py` — RFC 8032 §7.1 plus refusal controls. Run in the pinned interpreter the slots exec | mechanical, in `make test` |
| a verdict silently depends on a posture nobody recorded | the suite records the grant the handshake issued (`handshake_grants`) and whether each declared grant precondition held; core-go's launch record is written by `make peer-up` and read, never typed (`F43`); collection records WHICH BUILD of the peer ran (`peer_tree`: HEAD + uncommitted-diff digest) and `tools/differential.py` refuses to compare across a different build (`F50`) | mechanical, in every report and the differential |
| a category is called done without running | the category's `RUN-*` document with the differential, the triage table and what it does NOT show | procedural, reviewed at the category's close |

**Not yet enforced, and said so:** "implemented by a suite" is what the gate counts; "run against peers this
snapshot" is not machine-checked. Output is not committed, so a gate cannot see it without inventing a committed
run ledger. Earn that on an incident, not in advance (`AP-3`).

---

## D15 — a negative is claimed only over a region that could have contained the positive

**Trigger:** writing "X does not exist", "nothing defines X", "no check measures X", "the oracle is blind to X", or an
empty `oracle_check` · reading an ORACLE BLIND row · any bounded negative in a finding or a requirement file.

> **Name the region searched, and say why the thing would be visible there if it existed.** A register of declaration
> sites cannot show a check named at runtime; a live corpus cannot show the archive. A search over a region that could
> not have held the answer is a statement about the search.

**Why it is a discipline and not advice:** it bit twice, in two shapes. `AP-1` (2026-09-11, `F7`): *"defined nowhere"*,
searched over two spec trees, while the definitions sat in the archive. `AP-1`, second instance (2026-09-13, `F54`): *"the
floor's negotiation row is measured by 0 of 1239 reference checks"*, searched over the check **register**, while the
**executed** set carried `connectivity/connect_incompatible_protocol` and `connect_absent_protocols`. The register lists 5
connectivity checks and the oracle runs 38; the other 33 are named at runtime. The export had warned about that gap
(declared 201 against executed 778) two days before the finding was written. Arch had called F4 the best finding of the
track, so a wrong negative travelled a long way.

**Enforcement:**

| Shape | Enforcement point | Kind |
|---|---|---|
| "the oracle has no check for this requirement" | `tools/differential.py` — for every ORACLE BLIND row, lists each **executed** oracle check citing a core section the requirement cites (§9 excluded), every run, under *"ORACLE BLIND is a negative — check it"*. A real join is written into the file's `oracle_check`; a non-join is recorded in the run's triage | mechanical listing, in `make differential`; the disposition is procedural |
| "X is defined / specified / implemented nowhere" | the finding carries its **region list**, and that list includes the archive or says why not (`AP-1`'s rule) | procedural, at authoring; no grep can check it, and that is said rather than hidden |

**Not yet enforced, and said so:** the section match only catches a check that cites a section the requirement also
cites. A check exercising the obligation while citing something else is still invisible. Keyword matching was not added:
the first incident was a citation match, and a broader net with no incident behind it would be `AP-3`.


## D16 — a run-defining input the inputs already carry is DERIVED, never restated in the instrument

**Trigger:** writing any constant in a suite or harness that names a snapshot, a posture, a peer, a spec version, a
grant, or a declared limit · adding a field to the verdict document · reviewing a report whose `spec`, `posture` or
`peers` block reads the same on every run.

> **If the input exists as data on the way in, the instrument reads it. It does not restate it.** A restated input
> cannot disagree loudly with the real one — nothing compares them — so it disagrees silently, and it disagrees on
> the verdict document, which is the only thing a second instrument can be compared against.

**Why it is a discipline and not advice:** it bit twice, in two cells. `F43` (2026-09-13 b): the core-go posture typed
by hand into `make core-go-s1` and `collect-run.py`, while `peer-up` had already observed and recorded it. `F65`
(2026-09-14): `suites/py-prototype/run.py` `SNAPSHOT = "core-0.8.2.21"`, a module constant stamped into every verdict's
`spec` block, while **every requirement file carries its own `snapshot`** and `spec-data/README.md` rule 3 makes that
field mandatory *so that a result can be re-verified against the text it measured*. Both constants were **correct when
written**, which is the whole difficulty: a correct constant is indistinguishable from a derivation until the day the
input changes, and for `SNAPSHOT` that day is the first re-base — when some requirements cite `core-0.8.2.21` and some
`core-0.8.2.24` and one literal is stamped over both.

**This seat has less excuse than any other.** The founding incident is this shape: the posture decided the
measurement, was chosen once by one party, and was never written down — *because there was no field to write it in*.
`F65` is the worse version, because the field existed, was populated, and the instrument overwrote it with a guess.

**Corollary — a run has a SET, not a value.** A verdict spans snapshots legitimately: mid-re-base within one area, and
always once a peer is measured against core plus N extensions at N versions. `spec.snapshots` is a sorted set with a
`homogeneous` flag and a per-requirement map. The same will be true of `posture` and of `peers` as cross-peer rows
land. **A scalar where the domain is a set is this discipline's next instance waiting to happen.**

**Enforcement:**

| Shape | Enforcement point | Kind |
|---|---|---|
| a suite constant naming a `spec-data/` snapshot | **`make lint-suite-constants`** → `tools/suite-constants-gate.py` — reads real **string literals** (Python via `tokenize`, others comment-stripped) and refuses any that names a live snapshot path or version leaf; **four planted defects and four prose controls run first**, so it is shown able to fail *and* shown not to fire on a comment. In `make lint` | mechanical, gated |
| the posture | `peer-up` records it; `collect-run.py` and the suite read it; the suite also records the grant **as observed on the wire** and whether each declared precondition held (`F43`, closed) | mechanical |
| a new verdict field | at review: *is this value already present in an input this run reads?* If yes it is derived. If it genuinely is not, that absence is the finding — it is what `DESIGN-THE-SUITE-CONTRACT` §2 faults the reference oracle for on six fields | procedural |

## D17 — CANDIDATE — enumerate what governs a subject by LISTING, before designing against it

**Status: CANDIDATE, one instance.** Applied now; **not claimed to generalize** until a second instance in a
different shape (the promotion ladder in `docs/PROCESS.md` §4). A discipline added on speculation is removed if unearned within
a release cycle, and this one is deliberately parked on that clock.

**Trigger:** starting work on a subject · inheriting a charter, handoff or bring-up package · citing a document
this repo has not opened · writing "exhaustive search" about another repo.

> **Before designing against a subject, enumerate the documents that govern it — by LISTING THE OWNING REPO'S
> DIRECTORIES, not by searching for names you already know — and read the ones that bind you, from source.**

**Why it is not already `D12`.** `D12` says *never paraphrase canonical material from a handoff* — it governs
what you do with a derivative artifact you are holding. **It does not require you to find the documents the
handoff never mentioned**, and that is the gap this seat fell through: we obeyed `D12`'s letter about the
material we had, and the material we had was a bounded subset nobody could see the edges of.

**The incident (`F68`, `AP-14`):** four sessions, a charter citing four sections of `GUIDE-CONFORMANCE`, and
nobody had opened it. Every citation was accurate. The cost was the omissions — `SPECIFICATION-FORMAT` §8.5's
*declare your conformance class* `[MUST]`, unsatisfied by all 50 requirement files, and `GUIDE-CONFORMANCE`
§7.0's taxonomy, which has no row for what this seat produces.

**Why LISTING and not searching is the operative word.** Every search this repo ran hit `specs/`. `guides/` is
its sibling, holds ~40 documents including the one that governs our entire subject, and **no name-based search
would ever have surfaced it**, because you cannot grep for a document whose existence you do not suspect. This
is `D15`'s own rule — *a negative is claimed only over a region that could have contained the positive* —
violated by `D15`'s author, which is the argument for making it mechanical.

**Enforcement:**

| Shape | Enforcement point | Kind | State |
|---|---|---|---|
| a document we cite but have never read | **a source inventory with a per-document read state**, defaulting to `unread`; `partial` must name its sections | procedural, but the state is a value something prints | ✅ landed 2026-09-14 |
| a citation to a document not in the inventory | **`make lint-sources`** — refuses a cited document with no inventory entry, and an entry with no read state, with planted defects. It also ratchets **how much material we rely on without having read**, which may only go down | mechanical, gated | ✅ landed |
| "we searched exhaustively" | the finding names the **directories listed**, not the terms grepped | procedural, at authoring | ✅ inherits `D15` |

**What would ratify it:** a second instance in a different shape — e.g. a sibling seat's contract adopted from a
summary, or an ADR cited by number and never read. ⚠ **The second is already half-present:** `[ADR-0002]` and
`[ADR-0012]` are load-bearing in our routing packets and **neither has been read as a document**. If that
produces a defect, `D17` ratifies.

## D18 — CANDIDATE — a name that will appear in a path, an id or a published number is taken, never coined

**Status: CANDIDATE.** From `ADR-0001` §7, which proposed it as "`D17`" — **that number was allocated to the
discipline above in the same session, by a different document, and neither could see the other.** Renumbered
here, and the collision is itself the smallest possible instance of the rule: *two seats coining the same
identifier in parallel because neither enumerated what was already taken.*

**Trigger:** creating a directory, a file-name convention, an id prefix, a suite name, a verdict field — anything
that will be typed by someone who was not in the conversation that chose it.

> **A name that will appear in a path, an id, or a published number is taken from the document or repository it
> refers to, lowercased and unabbreviated — never coined. Where no such name exists, the naming is ROUTED before
> it is used.**

**The instances, and what each cost:**

| Name | What was wrong | How it bit |
|---|---|---|
| **`spec-data/core-<version>/`** | `core` is an **abbreviation this seat invented**, and it collides with **core profile** — a real and different thing used constantly (`--profile core`, 16 core-profile categories, 201 core-profile declarations) | `requirements/core/` **read as *core-profile requirements* and meant *core-protocol requirements***. The directory also names one of the three documents it holds, so `ENTITY-CBOR-ENCODING` moving 1.6 → 1.7 inside `core-0.8.2.24` was invisible in the name |
| **`suites/s1-py/`** | `s1` encodes **creation order**, which nothing needs | It has **already named two different instruments**: `s1-go` existed, was retired 2026-09-13, and the ordinal was silently reused |
| **`D17` itself** | two documents allocated the same discipline number on the same day | Caught by a reader, not by a gate — which is the whole point below |

**Why it needs to be a rule and not taste.** Every one of these survived four working sessions and a green
`make check` every time. **A gate cannot see a name**: every instrument in this tree checks *content* — digests,
ids, schema, planted defects — and none of them can tell you a directory is called something nobody uses. The
skeleton came from arch's bring-up handoff; **every name below the top level was chosen by a session here, in
passing, while doing something else, and inherited by the next session as though it had been designed.**

**Enforcement:**

| Shape | Enforcement point | Kind | State |
|---|---|---|---|
| `requirements/<spec>/` drifting from `spec-data/<spec>/` | **`tools/requirement-gate.py`** — three independent checks with planted controls: a file outside the mirror, a spec directory with no `spec-data/` counterpart, and a path whose `snapshot` field names a different spec. In `make lint` | mechanical, gated | ✅ landed 2026-09-15 |
| a coined name anywhere else (suite names, verdict fields, id prefixes) | at review, and in the ADR that introduces it: **name the document or repo the name is taken from.** `ECP` is arch's; `py-prototype` is the language plus what it is | procedural | ⬜ no mechanical point — **and this is why the discipline stays CANDIDATE** |

**What would ratify it:** a third instance in a shape the mirror gate cannot catch — most likely a coined field
name in the verdict document or a coined id prefix. **`ADR-0001` §5 has the live risk already:** if suites
declare a spec set, that axis needs a name, and there is no existing document to take one from.
