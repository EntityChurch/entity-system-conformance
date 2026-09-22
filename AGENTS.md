# entity-system-conformance

Read **AGENTS-STANDARD.md** first. This file adds this repo's specifics.

**Our addressable name is `entity-system-conformance`** — the repo's directory name, and what a
packet's `To:` line must say to reach us. We send from `docs/outbox/`.

> **If you are reading this in the published repository, some paths below will not be there.**
> This file is the working document of the seat that builds the instrument, and it is published
> because it is the honest answer to *"how does this project actually work"*. Three directories it
> names are deliberately internal and do not ship: **`docs/status/`** (dated session material),
> **`docs/outbox/`** (routing between seats), and **`docs/agents/memory/`** (what this seat has
> learned, not yet written for an outside reader). Nothing in them is a prerequisite for using or
> checking anything here. **`docs/PROCESS.md` is the same method written for you**, and
> `README.md` is the way in.

---

## L0 — what this seat is for, and the one rule that protects it

**We build the independent conformance instrument: a neutral statement of what the protocol
requires, and N independently built test suites over it.**

**The threat model, stated once, because every rule below follows from it.** A single oracle cannot
distinguish *"the peer is wrong"* from *"the oracle is wrong"* — every check it runs is scored by
the same judgement that wrote it, so its own errors are invisible **by construction**. And an
oracle's bug does not stay in the oracle: every peer is fixed until it passes, so the bug becomes
the observed behaviour of the whole cohort, and then it is indistinguishable from the protocol.
**We are here to stop one implementation's mistakes being canonicalized as the standard.**

### The three prohibitions — each one is a way of becoming the thing we were built to check

1. **⛔ NEVER SHIP A PEER.** The moment this repo implements the protocol, it is writing its own
   exam. When a check needs a behaviour no available peer provides, that is **a finding routed to
   the peer's owner** — never a peer built here. This will be tempting and it will be tempting
   early.
2. **⛔ NEVER AUTHOR THE SPECIFICATION.** We state what the spec requires; we do not decide it.
   An ambiguity is routed to the architecture seat. *A requirement we invented is a requirement
   nobody agreed to, and a suite that passes it proves nothing.*
3. **⛔ NEVER READ THE REFERENCE ORACLE'S SOURCE WHEN AUTHORING A REQUIREMENT.** Requirements come
   from the **spec**. The reference oracle is a source of *coverage questions* — "what does it test
   that we have no requirement for?" — and never a source of expected values. **Transcribing it
   makes us a second copy of it**, which costs everything and measures nothing.

### ⛔ THIS FILE CARRIES NO RECORDED RESULTS — the rule that protects prohibition 3 from us

**`CLAUDE.md` → this file is injected into an agent's context by the harness before its first
turn.** A suite author cannot decline it. That is not a hazard we can gate away.

⇒ **The remedy is not a gate on the author. It is a constraint on this file.**

> **No verdict · no peer outcome · no measured per-requirement result · no expected value · no
> digest of an obligation.** Not in a table cell, not in a parenthesis, not as an illustration of a
> rule. **A recorded result reaching a fresh author is an answer key delivered before their first
> instruction**, and a suite that agrees for that reason is worse than no suite, because it reads
> as confirmation.

**What this file carries instead:** the prohibitions, the triggers, the rules, and *pointers* to
where results live — `docs/status/RUN-*`, `suites/CONTROL-SET.diag`, the ratchet ledgers. **None of
those is injected**, all of them are one deliberate read away, and every one of them is on the
forbidden-reading list for a suite author by construction. The incident that earned this rule, and
what it means for the next suite author, are in `docs/agents/memory/SUITE-INDEPENDENCE.md`.

⚠ When you catch yourself adding *what a peer did* here to make a rule land harder, the rule is not
the thing you are adding.

### And we are not the only scorer either

`entity-core-go`'s `validate-peer` **stays, permanently.** Not forked, not deprecated, not
replaced. It is the standing independent implementation and the failsafe that makes ours checkable
— the same argument that justifies us, pointed at us. **Disagreements between two instruments are
adjudicated by the architecture seat, not by whichever of us is louder.**

---

## What a disagreement IS

**A disagreement between two conformance instruments is the product, not a defect.** When our suite
and the reference oracle differ on one peer, exactly one of three things is true, and finding out
which is the job:

| | Outcome |
|---|---|
| **Specification gap** | the requirement was ambiguous — route it upstream, the spec gets refined |
| **Implementation bug** | the peer is wrong — route it to the peer's owner |
| **Check bug** | one of the two suites is wrong — fix it, in both if the gap is shared |

**Never resolve a disagreement by re-running it.** A rerun is what you do to a flaky measurement;
this is not a flaky measurement, it is two judgements differing, and the difference is the
information.

**This is why requirement-keying is non-negotiable.** *"Oracle A passes and oracle B fails"* is
unanswerable. *"We disagree about `COMP-R7`"* is a well-posed question with an owner. A suite that
reports only its own check names has produced noise.

---

## The multi-suite model — **`requirements/` and `suites/` are separate on purpose**

```
spec-data/<spec>/v<version>/               the pinned text, MANIFEST.md authoritative per document
requirements/<spec>/<PREFIX>-R<n>.diag     one neutral requirement, one file (CBOR diagnostic notation)
suites/<name>/                             an independent implementation of them
```

⭐ **`<spec>` is the specification's own repository or document name, lowercased — never an
abbreviation, never a word coined here — and `requirements/<spec>/` mirrors `spec-data/<spec>/`
name-for-name** (`ADR-0001`). `tools/requirement-gate.py` fails the build when a requirement's path
and its `snapshot` field name different specs.

**Any number of suites, and that is the point rather than a contingency.** Different languages,
different authors, ideally built without reading each other. **Build the same thing from the same
neutral statement enough times and the statement stops being ambiguous.** We expect the first two
or three suites to be expensive and to surface most of the ambiguity, and later ones to be cheap
and boring. **When a new suite finds nothing, that is the finish line** — and we will have measured
it rather than assumed it.

- **A suite declares which requirements it implements.** Partial is normal and expected; a suite
  claiming universal coverage on day one is a suite that is transcribing.
- **Coverage is reported jointly**: *"suite A reaches 24 of 38 binding rows, suite B reaches 19,
  together 31."* That sentence is the reason for the `requirements/` directory.
- **Do not share code between suites.** Shared code is shared bugs, and shared bugs are exactly the
  thing two suites exist to not have. Sharing the *substrate* (peer launching, transport) is fine
  and expected; sharing *assertions* is not.
- **⛔ No suite in the reference oracle's language (Go), and no suite on a library the cohort
  shares.** Cryptography and codecs come from the RFCs. The *runner* (make targets, `tools/`) may
  be anything. `make lint-suite-independence` holds it.

---

## Every peer is a candidate reference peer — the fairness rule

> **A cross-peer check MUST NOT fix the language of the other side.** The peer pair is a
> **parameter**, and any peer that passes the floor is a candidate for either end.

We have peers in abundance — the anchor generates dozens — so there is no reason to privilege one.
**The target is every peer against every other**, and where the full matrix is too expensive, the
pairs actually run are **declared**, never left implicit. A cross-peer result that does not say
which two peers produced it is not a result.

## Declare the posture — the rule this seat was founded on

> **A check declares the preconditions it assumes — granted scopes, seeded identities, installed
> handlers — as DATA. A precondition stated only as English inside a skip message is not declared.
> Every verdict records the posture it ran in.**

Both of these are the same defect at two levels: *an input that decides the outcome, chosen once,
by one party, and never written down.* **The measurements that earned them, and what a posture file
actually is, are in `docs/agents/memory/POSTURE-AND-PEER-SELECTION.md` — read it before any peer
run or any number about a peer.**

---

## `requirements/` — the authoring rules

A requirement is **one independently failable obligation**. If a conversion produces something that
is really two obligations, that is **a finding to file**, not something to quietly split.

Each carries: the id (`SPECIFICATION-FORMAT` §8.5a's `<PREFIX>-R<n>`, allocated once, never
renumbered) · the spec sections · the snapshot it was authored against · the MUST/SHOULD level · a
**reading** that quotes the normative text and argues the interpretation · the observable surface ·
the preconditions as data · and **both arms** — what a conformant peer does *and* what a
non-conformant one does.

**A check that cannot be made to fail has not been shown to measure anything.** Every requirement
needs a negative control, including — especially — the ones that can never fire against a correct
implementation.

⛔ **The prior art you are required to have read before designing any of this is listed in
`docs/agents/memory/REQUIREMENT-AUTHORING.md`**, in order, starting with
`entity-system-architecture/guides/GUIDE-CONFORMANCE.md`, which governs this subject and which this
repo cited for four sessions without opening. That file also carries the four ways this seat has
got a requirement wrong.

---

## The bring-up sequence

**Step 1 is an export, not a design.** Walk `validate-peer`'s checks, and for each one ask *"what
requirement is this measuring?"* — then write that requirement from the **spec**, in neutral
language. The oracle tells us *what surface has been thought about*; the spec says *what is
required*. Where the two disagree, that is the first finding, and it arrives before any suite
exists.

**Expect the specs to be insufficient at first, and say so loudly when they are.** The architecture
seat expects this and will refine them. *"I do not know what this is trying to test"* is the most
valuable sentence this repo produces in its first months — it is never a failure to report it, and
sitting on it to look competent is the one behaviour that wastes the whole exercise.

| # | Step | State |
|---|---|---|
| 1 | Read `docs/STATUS.md` for where the work is, then `README.md`'s reading order | — |
| 2 | ~~Export the reference check set → the requirement questions it implies~~ | ✅ `docs/status/EXPORT-*`. **Re-take it; it is HEAD-pinned and moves** |
| 3 | ~~Pin a `spec-data/` snapshot~~ | ✅ current pin in `spec-data/README.md`; the distance to upstream is declared there, never assumed closed |
| 4 | **Run the loop below, one category at a time**, starting with the fully-resolved core categories | ⚠ **Partly done, and which part is a RESULT: read `docs/status/RUN-*` for what each category actually did, and `requirements/UNEXECUTED-CEILING` for the count.** Not restated here — see the no-recorded-results rule above |
| 4b | **The bring-up sequence is written down** — `docs/WORKFLOW-SUITE-BRINGUP.md`, ten stages, each graded by whether it has ever caught a real defect | ⭐ **Two stages are graded MISSING and both are at stage 4/8** — nothing enforces author separation, and `lint-peer-diversity` clause 2 is unimplemented |
| 5 | ~~Build **suite 2**: a third language (not Go, not Python), a different author, without reading `suites/py-prototype`~~ | ✅ `suites/rs-conformance`, from `docs/BRIEF-SUITE-2.md` and nothing else |
| 5b | **Suite 3, and the rule it tests** | The floor is *"a new suite finds nothing"*, and two suites have not reached it. ⛔ **Before standing one up, apply the no-recorded-results rule to every artifact the author will be handed**, this file included. `requirements/UNSPLIT-CEILING` is what the next suite will hit; `docs/agents/memory/SUITE-INDEPENDENCE.md` says why |
| 6 | Repeat until a new suite finds nothing | |

### ⛔ The loop — a category is not done until it has run on real peers (D14)

**Author → implement → run → compare → triage → feed back, per category, before authoring the
next.** Fifty requirement files were written, reviewed and gated before one was run (`AP-9`); the
first run found a requirement defect in minutes that three review passes had not. Every step is a
make target:

`make test build` → `make keystone-s1 keystone-oracle` → `make generator-s1 generator-oracle` →
`make peer-up core-go-s1 core-go-oracle` → `make differential` → triage every non-AGREE row → fix
the requirement or file the finding → lower `requirements/UNEXECUTED-CEILING`.

**Peers: Keystone and the generator FIRST, core-go last** — they are the ecosystem's standardized
slots and cover most of the cohort; core-go is one bespoke implementation. **A disagreement is
triaged, never re-run.** **Agreement is not coverage:** `make differential` lists every check the
oracle executed with no requirement of ours, and that list is the next batch's worklist.

⚠ **Which category to start with, and which not to, is in
`docs/agents/memory/REQUIREMENT-AUTHORING.md`** — along with the check-set numbers that count
different things and are both right.

---

## Boundaries — do NOT modify

- **`AGENTS-STANDARD.md` / `METHODOLOGY.md`** — injected verbatim (`[ADR-0010]`). You may edit them
  when you judge a change justified; the next publish reconciles it.
- **Every other repo.** Peers, the anchor, the generation seat, the spec repos, meta — read-only.
  Cross-repo coordination is a routing packet, never an edit.
- **Consumed peers** — never vendored here and never patched here. Peers are reached through
  Keystone's census driver and the generator's `host-launch`, in their own trees; a defect in one is
  **routed to its owner**, which is prohibition 1 restated as a boundary.
- **`spec-data/`** — another project's text, copied unchanged under its own licence. Never edited
  here, for a reason that is now also a licence term. See `spec-data/entity-core-protocol/PROVENANCE.md`.

---

## Memory — what this repo has learned

**`docs/agents/memory/` holds what you would otherwise rediscover the hard way. Read
`docs/agents/memory/INDEX.md` first** — it has a row per topic and a symptom table, and it is read
**on demand**, never in full at session start.

This file carries what you need *before* your first change. Anything you need only when you hit the
thing it describes belongs there instead — and **an entry that could become a check should become
one, and then it comes out of memory.**

## Methodology tier — **CORE**

D1–D12 + native · the Audit doctrine · the anti-pattern catalog · review questions. **Own
disciplines numbered from D13**, earned on our own incidents.

| Trigger | Open |
|---|---|
| ⭐ **starting ANY session, and before authoring a line** | **`make inbox`** — delivery here is PULL and this is the only thing on our side that pulls. ⛔ Not in `make check`: check must run with no sibling tree, and **an empty inbox and an unread inbox print the same thing.** ⚠ It counts PACKETS — count the asks yourself. Details and the two ways it has been blind: `docs/agents/memory/ROUTING-AND-COUNTERPARTS.md` |
| ⭐⭐ **standing up a suite, picking the chunk it builds against, or asked "do we have a process or a habit?"** | **`docs/WORKFLOW-SUITE-BRINGUP.md`** — ten stages, each with an honest state (**SOLID** = has caught a real incident · **BUILT** = never fired · **MANUAL** · **IMPROVISED** · **MISSING**). ⛔ **The chunk criterion is not negotiable: a requirement is fit for bring-up only when BOTH outcome classes have been observed on real peers**, because a suite reporting FAIL everywhere and a suite that is simply broken produce identical output. Enforcement: `suites/CONTROL-SET.diag` + `make lint-control-set` |
| ⭐ **about to trust a recorded verdict — a run document, a control row, a remembered number** | **`suites/CONTROL-SET.diag`**'s `staleness` block. **Every verdict carries the sha256 of the obligation it was scored against, or it is not evidence.** ⛔ **And the control set is an ANSWER KEY to nobody**: a new suite disagreeing with a row is one of the three outcomes, never automatically the new suite's fault |
| starting a requirement batch, taking a snapshot, or claiming "read / pinned / covered" | **D13** — `docs/DISCIPLINE-CHARTER.md`: scope is set by what the spec declares normative, never by a pointer into it |
| about to author, review, or call a requirement "covered" | **D14** — `docs/DISCIPLINE-CHARTER.md`: a requirement is not landed until a suite has run it against real peers |
| writing a negative — "nothing defines X", "no check measures X", an empty `oracle_check`, an ORACLE BLIND row | **D15** — `docs/DISCIPLINE-CHARTER.md`: claimed only over a region that could have held the positive; the register is not the executed set |
| about to author or review a requirement | `docs/agents/memory/REQUIREMENT-AUTHORING.md`, then `docs/ANTI-PATTERN-CATALOG.md` — which is the catalog's full range, not a remembered prefix of it |
| ⭐ **RE-AUTHORING a requirement against a new snapshot, or about to RUN one** | **`AP-18`** — the requirement moves and the INSTRUMENT does not, and **every gate here measures the declaration.** ⇒ Re-authoring is not done until the check is re-read against it and `IMPLEMENTS`' second column is updated. Enforcement `make lint-implements`, debt `suites/IMPLEMENTS-REVIEW-DEBT` |
| ⭐ a requirement whose `spec` or `reading` quotes a **§9 row** rather than the body it summarizes | **`AP-16`** — a requirement transcribed from a conformance **inventory** inherits that inventory's defects, and no care in the transcription detects one. Quote the body too, and say whether the two agree |
| ⭐ splitting a requirement, authoring an item, or picking an item id | **`ADR-0003`** — the obligation and the probe are two objects, and `drives` is the only join between two suites. `D18`: item ids are **derived**, never coined |
| ⭐ about to report a run, a coverage number, or a peer's result | **`ADR-0003` §7** — the peer set is **declared data** (`suites/<name>/PEERS.diag`, `make peers`), and a verdict records the peer's **identity**, never its name. ⚠ **A pin says WHICH BYTES; a certification says they were CHECKED**, and most of the cohort is pinned and not certified — `make peer-identity PEER=<n>` says which, per peer |
| ⭐⭐ **asked "how deep does this go", "what checks the checker", or about to claim a result is INDEPENDENT** | **`docs/MODEL-THE-MEASUREMENT-STACK.md`** — the four layers, and **§3 the independence ledger**, which is the one thing to read if you read one thing. ⛔ **Every count in this ecosystem flatters us.** §4 is where the regress actually stops: outside the ecosystem (RFCs), in a construction rather than an authority, or in an adjudicated disagreement. **Never in more peers, more runs, or agreement** |
| a counterpart with no `TRACKER-*` file, or one that seems to have gone quiet | **there is no such thing as a quiet counterpart — only an unenumerated one.** `docs/agents/memory/ROUTING-AND-COUNTERPARTS.md` |
| relying on a quotation — from a handoff, a packet, or a counterpart | **`AP-14`** (→ `D12`, enforcement point `make lint-sources`) — a counterpart's *accurate* quote still bounds what you know, because it cannot carry the shape of the document it came from |
| ⭐ **two implementations of one rule in this tree, and nothing between them** | **`make lint-codec-agreement`** — two canonical-CBOR encoders disagreed here for the repo's entire life and nothing compared them. ⚠ **Before adding a third implementation of anything, add the comparison first** |
| about to start or change a suite, or pick its language | `docs/agents/memory/SUITE-INDEPENDENCE.md` + the suite's own `README.md` |

## Build

`make help build test lint fmt check clean`, container-default with a `-native` opt-in. `build` is
the prototype suite (`suites/py-prototype`, Python 3.12 stdlib only) bundled with a **pinned**
standalone interpreter and musl loader into `output/bin/py-prototype{,.d}`. `test` runs, in that
interpreter, the codec against the snapshot's ECF corpus and Ed25519 against RFC 8032. `lint`
includes the executed-by-a-suite ratchet and `lint-suite-independence`. The run targets are in the
loop above; `make help` lists them. `fmt` is a no-op that says so — there is no formatter in the
host contract and the corpus is canonical-CBOR-gated rather than formatted.

⭐ **`build` knows exactly ONE suite, and the RUN PATH knows none — `SUITE=<name>`.** A suite that
is not suite 1 is **DELIVERED, not built here**: drop the executable at `output/bin/<name>` and
declare `suites/<name>/{PEERS.diag,IMPLEMENTS}`. **`make require-suite SUITE=<name>` names which is
missing.** Enforcement: **`make lint-suite-slot`**.

⚠ **What the build assumes about the host, the one network fetch it makes, and why `make help`
opens with a `COULD NOT LOOK` line, are in `docs/agents/memory/BUILD-AND-THE-RUN-PATH.md`.**

**Four ratchets, all down-only, all printed every run.** `requirements/UNEXECUTED-CEILING` (D14, a
requirement no suite has run) · `requirements/UNSPLIT-CEILING` (ADR-0003, obligation and probe still
fused) · `docs/SOURCES-CITATION-DEBT` (D12, material we rely on unread) · `suites/IMPLEMENTS-REVIEW-DEBT`
(AP-18, checks never read against the obligation they measure). **Each ledger states its own current
figure and `make lint` prints all four every run; none is restated here, because a number copied
into an injected file is stale the moment it is copied and reads as current forever.** **Lowered
only by doing the work, never by editing the number.**

## Publication

⭐ **THIS REPO PUBLISHES.** `CANONICAL-DOCS.toml` is the whole interface — we declare, the release
pipeline publishes, and which files reach public `master` is not ours.

- **A declared file is addressed to a reader OUTSIDE this ecosystem.** Not to the next session, not
  to a counterpart seat. Ecosystem operations — packet stems, tracker rows, finding ids, who ruled
  what and when, internal paths — do not belong in one.
- ⛔ **An undeclared prose file under `docs/` is DROPPED from the public tree, silently.** So a
  published document that links to an undeclared one ships a broken link. **Declare the target or
  do not link it.**
- ⛔ **A commit SHA in a declared file resolves to nothing** — published history is authored fresh
  at the release boundary. Cite by content digest, release tag, or the content itself
  (`[ADR-0012]` Am. 1). Internal documents under `docs/status/` and `docs/outbox/` are unaffected:
  cite SHAs there freely.
- **`docs/status/**` and `docs/outbox/**` are never published.** `docs/STATUS.md` is the *public*
  status and is written for that reader; **next-session continuity belongs in a
  `docs/status/HANDOFF-*`.**
- **Non-prose is never dropped**, so `requirements/<spec>/*.diag`, `suites/**` and `spec-data/**` publish
  as code whether or not they are declared. **Anything you would not publish must not be written
  into one of those paths.**

Push to `origin` only; public forges are never an agent's to push.
