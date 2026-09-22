# WORKFLOW — bringing up a conformance suite, end to end

**What this is.** The sequence for standing up a new independent test suite, from "we have a
specification" to "we have a second opinion we can trust." Ten stages. Each one says what it
produces, what enforces it, and — **the reason this document exists** — whether that stage is
actually built or is improvised fresh every time somebody walks through it.

**Who it is for.** The operator deciding whether this seat has a process or a habit; and the session
that runs it. **It is not the brief handed to a suite author** — that is `docs/BRIEF-SUITE-2.md`, and
the author is deliberately given far less than this.

**Written 2026-09-16**, on operator direction, before building suite 2 rather than after. The
direction was: *map it out, understand each piece, and say whether each piece has been refined and
solidified or is being half-assed as we go.* **The `State` column is that answer and it is not
graded generously.**

---

## 0. The honesty scale used in every `State` cell

| | Means |
|---|---|
| ✅ **SOLID** | Built, has an automated enforcement point, **and has caught a real incident.** Shown to work by failing when it should. |
| 🔵 **BUILT** | Built and gated, **never fired on anything real.** It may be correct. Nothing has demonstrated it. |
| 🟡 **MANUAL** | A written procedure a person follows. Repeatable, no automation, **nothing detects skipping it.** |
| 🟠 **IMPROVISED** | Done once, by hand, by whoever was there. No artifact, no procedure, **not reproducible by the next session.** |
| ⛔ **MISSING** | Named here because the sequence needs it. Does not exist. |

**The rule behind the scale:** a stage is only `SOLID` if we can point at the day it stopped
something. Everything else is a claim about the future.

⛔ **One grade per stage, and it is the WEAKEST part that binds.** The first draft of this document
gave two stages a split grade — *"SOLID as a rule, IMPROVISED in the one place that matters"* — and
that is how a stage hides behind its better half. If the packaging is manual, the stage is manual,
however good the specification is.

**Current: 4 SOLID · 2 BUILT · 3 MANUAL · 1 MISSING.**

⛔ **Stage 1 went from SOLID to MANUAL on 2026-09-16 (c), and a downgrade is the only honest
direction that grade could move.** Nothing about stage 1 got worse; **what it was graded on was
wrong.** It was scored on the digest manifest, which is genuinely solid, while the thing that
actually binds — *does anything make us re-pin when the specification moves?* — had never been
asked, because the stage was written as a one-time act. The spec then moved three revisions past our
pin and falsified a requirement in the bring-up chunk.

> ⭐ **A grade that has only ever gone up is a grade nobody has re-derived.** Every other stage here
> was graded once, by the session that built it, against the criteria that session chose. **Stage 1
> is the first one re-graded by someone asking a different question**, and it fell.

⚠ **The earlier claim — that stages 3 and 7 improved *"not because anything was regraded"* — still
stands and is not withdrawn.** Both moved because artifacts were built and one caught a real defect.
**That remains a different act from this one.**

---

## 1. The ten stages

```
  ┌─ THE CORPUS (once per specification) ──────────────────────────┐
  │  1  pin the spec          2  state the obligations             │
  └────────────────────────────────────────────────────────────────┘
  ┌─ THE SUITE (once per suite) ───────────────────────────────────┐
  │  3  pick the chunk        4  pick the author + language        │
  │  5  build the checks      6  prove each check can fail         │
  └────────────────────────────────────────────────────────────────┘
  ┌─ THE VALIDATION (the part that makes it an instrument) ────────┐
  │  7  establish the control set    8  run against real peers     │
  │  9  compare to the other suite   10 triage, feed back, ratchet │
  └────────────────────────────────────────────────────────────────┘
```

**Stages 1–2 are shared across all suites. Stages 3–10 repeat per suite.** Stage 10 feeds back into
stages 1–2, which is the loop.

---

## 2. Stage by stage

### Stage 1 — Pin the specification

**Produces:** `spec-data/<spec>/v<version>/` — the documents copied verbatim, never edited here, plus
a `MANIFEST.md` recording a **sha256 per document** and why the snapshot was taken. Old snapshots are
never deleted, so a requirement written against an older one stays readable.

**Enforcement:** `make lint-spec-data` (`tools/spec-snapshot-gate.py`) — 4 snapshots, 22 documents
verified every run.

**State: 🟡 MANUAL — downgraded 2026-09-16 (c) from SOLID, and the downgrade is the finding.**

The *digest* half has fired and is genuinely solid: it caught two documents changing normative
content at `0.8.2.26` while their version headers did not move, which is only detectable because the
manifest pins content rather than version strings. That finding is routed.

⛔⭐⭐ **But the stage is graded on its weakest part, and the weakest part is that NOTHING TRIGGERS A
RE-PIN.** This document had ten stages and one feedback edge — stage 10 into stages 1–2. **There was
no edge for upstream specification movement at all**, because stage 1 was written as a one-time act:
*pin the spec, then work.*

> **The specification is not an input. It is a moving counterparty.**

**What that cost, measured the day it was written.** Our pin is `v0.8.2.26`. Upstream's committed
head is **`0.8.2.29`**, with `.30` uncommitted — **four revisions in six days**, and one of them
(`0.8.2.28`) **falsified the central reading of `ECP-R3`**, which was one of the two requirements
the bring-up brief was about to hand to a fresh author. The brief told that author the opposite of
the truth *and told them to distrust the correct answer if they found it.* **`make check` was green
throughout**, because every gate here measures a declaration and **the spec is the one input no
declaration of ours covers.**

⭐ **The structural statement, because it generalizes past this incident:** every artifact below is
pinned to the one above it — requirement to snapshot, item to requirement, check to item, control
set to check, brief to control set — **and nothing is pinned to the top.** A chain of tight local
pins with a loose anchor drifts silently and every link reports green.

**What would make this stage SOLID, and none of it exists yet:**

1. **A re-pin trigger with an owner.** Not *"re-pin when convenient"* — a named event: a counterpart
   packet announcing a version, or a periodic check.
2. ⭐ **A measured DISTANCE rather than a chase.** *"Our pin is N revisions behind upstream HEAD"*
   printed every run. **You cannot stop a counterparty moving; you can refuse to let the gap be
   invisible.** That is this seat's entire doctrine applied to its own input, and it is the cheap
   half.
3. **A rule for what a moved spec does to a requirement authored against the old one.** `AP-18`
   covers *requirement moved, check did not*. **There is no catalogued anti-pattern for *spec moved,
   requirement did not*** — and it has now happened.

⚠ **Chasing the pin is NOT the remedy and is explicitly rejected** (operator direction, 2026-09-16):
four revisions in six days cannot be tracked by a 50-file hand-authored corpus, and a seat that
tries will never finish anything. **Measure the gap, declare it, and build against the pin anyway.**
The brief now tells the author exactly this.

---

### Stage 2 — State the obligations, in our own words, from the spec

**Produces:** `requirements/<spec>/<ID>.diag` — one independently failable obligation per file. The
id, the spec sections, the snapshot it was written against, the MUST/SHOULD level, a **reading** that
quotes the normative text and argues the interpretation, and **both outcome classes** — what a
conformant peer does and what a non-conformant one does.

⛔ **The obligation file contains no test.** No bytes to send, no responses to accept. That split is
`ADR-0003` and it is what makes two suites possible at all: if the probe lives in the obligation
file, a second suite either copies the first suite's test or forks the obligation into two homes, and
both are forbidden.

**Enforcement:** `make lint-requirements` (50 files, 30 planted defects in its self-test) ·
`make lint-items` (the probes, 15 planted defects) · `requirements/UNSPLIT-CEILING`, down-only.

**State: 🟡 MANUAL — and this is where the operator's skepticism is correct.**

> *"I'm not really sold that you've actually converted them over or finalized what that format is."*

**Both halves of that are right, and they are different problems:**

| | Honest answer |
|---|---|
| **Is the format finalized?** | **The shape is real and gated — not a sketch.** A split file has been written three times and the gate refuses 30 distinct malformed shapes. **But it is `status: draft` on every file, it has never been reviewed by another seat, and the ecosystem's own authoring standard (`SPECIFICATION-FORMAT` §8.5a) separates a *requirement* from a *conformance item* in a way we have implemented but nobody has ratified.** |
| **Are they converted?** | **No. 3 of 50.** The other 47 still have suite 1's test fused inside them. **That is the honest number and it is the binding constraint on everything below** — a second suite can only be built against the 3. |

**What would make it SOLID:** the conversion is mechanical-looking and is not — §8.5a makes *"a
conversion that surfaces a requirement that is really two is a finding to file"* mandatory, and a
50-file batch pass cannot file findings because nobody stops to notice one. **So it is per-file, by
hand, and the rate is the rate.** Automation here would be the wrong ratchet.

---

### Stage 3 — Pick the chunk the new suite builds against

**Produces:** a named, justified subset of requirement ids.

**State: 🔵 BUILT.** Until this session the chunk was "whichever files happen to be split" — which is
availability, not a criterion. The criterion below is now written down AND mechanical:
`make lint-control-set` refuses a requirement declared fit for bring-up that does not have both a
PASS and a FAIL on real peers. ⚠ **BUILT rather than SOLID: the gate has not yet stopped anyone.**
The criterion caught the brief pointing at the wrong targets, but a person did that, not the gate.

⭐ **The criterion, stated for the first time. It comes straight from an objection raised against an
earlier draft: a bring-up chunk must not validate a suite against requirements whose correct outcome
we are not yet sure of.**

**A requirement belongs in a bring-up chunk only if both of its outcome classes have already been
observed on real peers.** If every peer we have fails a requirement, then a suite that reports FAIL
and a suite that is simply broken produce **identical output**, and we cannot tell them apart.

**Applied to what we actually have, measured 2026-09-16 at 13:03:**

| requirement | conformant arm | non-conformant arm | fit for bring-up |
|---|---|---|---|
| **`ECP-R3`** root-entity hash | ✅ 3 peers answer a coded `400` | ✅ core-go bare-closes | ⭐ **YES** |
| **`ECP-R57`** wrong root message type | ✅ 2 peers answer `400 invalid_request` | ✅ 2 peers, **in both required sub-classes** | ⭐ **YES — and it is the better target** |
| `ECP-R7` included-entity hash | n/a | n/a | **no** — ruled witness-only at `0.8.2.26`; produces no verdict on any peer |

**`ECP-R57` is the stronger validation target** because its non-conformant side splits across two
peers into the two sub-classes the specification requires be scored **separately**. A suite that
collapses them still gets the top-line verdict right on all four peers — **so only a control set that
records the outcome class catches it.**

⛔⭐ **Both of those rows were wrong when this section was first written six hours earlier, and the
correction is the most useful thing in this document.** The first draft read *"`ECP-R3` — the only
one"* and *"`ECP-R57` — 4 of 4 fail, a positive result is unobtainable."* Two things were wrong:

1. **The verdicts it rested on had been scored against requirement text that no longer existed.**
   `ECP-R3`'s file digest was `9714ce72…` in the morning run and `08155caf…` at HEAD — it was
   re-authored in between — and `ECP-R7` and `ECP-R57` had **both** moved too. ⇒ **This document
   walked into `AP-18` in the act of describing it.** Caught by checking the digests rather than by
   reasoning.
2. **Re-running all four peers against the current text changed the answer.** `ECP-R57` went from
   4 of 4 FAIL to **2 PASS / 2 FAIL**, which made it fit.

⭐ **And the reason it moved is now measured rather than guessed.** The three generator peers sit on
**one git head in both runs** — a reader tracking the cohort by commit would see nothing move and
would be wrong. The uncommitted-diff digest separates them: **the two peers carrying uncommitted
edits improved; the clean one did not.** Someone is fixing those peers right now.

> **That is the same finding as the spec version headers routed to the architecture seat this
> morning, one level down: a commit is not a content digest.**

⇒ **The pilot chunk is `ECP-R57` first, `ECP-R3` second, `ECP-R7` as an observer only.** The brief
offers all three as equals and calls `ECP-R57` unscoreable — **fixed in the brief, and stage 3 is
where it got caught.**

---

### Stage 4 — Pick the author and the language

**Produces:** a suite directory, and a declared author separation.

**Two independent constraints, and conflating them is how suite 1 failed the first time:**

1. **Language** — not the reference oracle's (Go), not an existing suite's (Python), and **no shared
   crypto or CBOR library.** Cryptography comes from the RFCs.
2. **Author context** — the author must not have read the other suite's source, its probe designs, or
   the 47 unsplit requirement files.

**Enforcement:** `make lint-suite-independence` holds constraint 1.

**State: ⛔ MISSING — graded on constraint 2, because the weaker half binds.**

Constraint 1 is ✅ SOLID — it has fired. Suite 1 was first written in Go, signed with the
same crypto library as the oracle and the reference peer, agreed with them beautifully **because it
shared their habits**, refused every CBOR float, and skipped 20 corpus vectors for reasons that were
about Go rather than about the protocol. It was thrown away and rewritten.

**Constraint 2 is ⛔ MISSING, and it is the sharpest gap in this document.**

> **Nothing enforces author separation, nothing measures it, and the only instrument is the honesty
> of whoever is writing.**

⛔ **Concretely and self-incriminatingly: the session writing this document cannot be suite 2's
author.** It has read suite 1's verdicts, its failure modes, the internal shorthand, and the recorded
answers for all three candidate requirements. **It knows what the answers are supposed to be.** A
suite it wrote would agree with suite 1 and the agreement would mean nothing — which is precisely the
failure this whole repo exists to prevent, arriving from the inside.

⇒ **The author is a fresh context that receives `docs/BRIEF-SUITE-2.md` and the three files, and
nothing else.** The brief already exists for this reason. **What does not exist is any check that it
was honoured** — no equivalent of `lint-suite-independence` for context, and it is not obvious one is
possible. **Named as unsolved rather than papered over.**

---

### Stage 5 — Build the checks

**Produces:** the suite's probes (`suites/<name>/items/`) and its runner, packaged to run inside each
implementation's own container.

**The interface is specified** — `docs/DESIGN-THE-SUITE-CONTRACT.md`: the invocation flags, and a
verdict document keyed on **requirement id**, never on the suite's own check names. A result without
a requirement id cannot be compared to another suite's and is noise.

**State: 🟡 MANUAL — graded on the packaging and on an unratified contract.**

- ⛔⭐ **Until 2026-09-16 (c) there was NO SLOT FOR A SECOND SUITE and nothing said so.** Every run
  target named `py-prototype` literally, at **25 sites**. ⚠ **The tools were already generic** —
  `collect-run.py` took `--instrument`, `peer-binding.py` took `--suite` — so the make layer was the
  only thing fixing the value, **which is exactly why no gate here could see it.** It would have
  been discovered on the day the author delivered a binary and there was nowhere to put it: after
  the expensive part, by the person least able to fix it. **Now `SUITE=<name>`, with
  `require-suite` naming the missing artifact and `lint-suite-slot` holding the line.**
  ⭐ **The lesson that generalizes: "pluggable" was asserted in the contract document and falsified
  by the one runner we own. A capability nobody has exercised is a claim.**
- ⚠ **The contract itself is marked *"first cut, not ratified"* and needs agreement from three other
  seats** — it is the interface a consumer swaps across, so until they agree, "portable" is a word.
- **Packaging is a real trap and it sank the first attempt.** The instrument is executed *inside*
  each peer's own toolchain image, where no interpreter is guaranteed. Suite 1 solves it by bundling
  a pinned standalone interpreter. **A static binary avoids the problem entirely, which is why the
  brief suggests one — as a practical note, not a rule.** `install-probe` no longer assumes a bundle
  directory exists.

---

### Stage 6 — Prove each check can fail

**Produces:** for every probe, a demonstrated negative control.

> **A check that cannot be made to fail has not been shown to measure anything.**

**Mechanically:** send the same input with the one thing under test **corrected**, and confirm the
peer answers normally. Without it, a peer that refuses *everything* passes your probe and you have
measured nothing.

**Enforcement:** the negative-control rule is mandatory in `tools/item-gate.py`, and when the arms
moved from requirement files to item files the rule was **re-planted in the new gate rather than
assumed to have survived the move.**

**State: ✅ SOLID — with a residue that no gate can close, named below rather than averaged in.**

⛔ **The rule was live and a control still broke, on 2026-09-16.** A control accepted **any**
response — including the exact refusal its own design said must void the probe. The gate checks that
a control **exists**; it cannot check that the control **asserts the right thing**. ⇒ **The control
is where to be paranoid, and it is the one place the automation genuinely cannot help.**

---

### Stage 7 — Establish the control set ⭐ *"the oracle for building the oracle"*

**This is the stage the operator named, it is the hardest one, and it is the least built.**

> *"It would have a set of peers that we theoretically know passed those tests … and then it will
> validate it, and then once it aligns — so we need an oracle for building the oracle."*

**The regress is real.** To trust a new instrument you need a known-good answer. The only existing
answers come from instruments whose trustworthiness is the open question. **If we validate suite 2
against suite 1's recorded verdicts, we have made suite 1 the oracle — and this repo exists because a
single oracle cannot distinguish "the peer is wrong" from "the oracle is wrong."**

**The way out is three controls of decreasing independence, used in this order. None of them is
"suite 1 says so."**

| | Control | Independent of? | State |
|---|---|---|---|
| **A** | **The constructed positive.** Corrected input → peer answers normally. Proves the probe reaches a live peer and the refusal is attributable to the thing under test. **Requires no trusted third party at all.** | everything | ✅ **SOLID** — it is stage 6's rule, per probe |
| **B** | **The known-arm peer set.** A requirement where *both* arms have been observed on real peers, so a suite reporting all-PASS or all-FAIL is detectably broken. **`ECP-R3` and `ECP-R57`**, 4 peers each. | suite 1's judgement; **not** independent of suite 1's *observation* | ✅ **SOLID as of 2026-09-16** — `suites/CONTROL-SET.diag` + `make lint-control-set`, **shown to catch the real incident** |
| **C** | **The external fixture.** RFC 8032 for signatures, RFC 8949 for canonical CBOR, and the specification's own 71-vector normative corpus. Answers written by people who never saw this ecosystem. | this ecosystem entirely | ✅ **SOLID** — `make test`, every build |

✅ **Control B was the gap and it was closed the day this document was written.**
`suites/CONTROL-SET.diag` declares, per requirement: the expected verdict **and outcome class** per
peer, the peer's pin, the posture, and — the field that earned the file — **the sha256 of the
obligation each verdict was measured against.** `make lint-control-set` recomputes those digests
every run, so a moved obligation reds the gate instead of silently invalidating the expectations
beneath it. **It is `SOLID` rather than `BUILT` because it caught a real incident before it shipped:**
the first draft recorded three passes that had been scored against requirement text which no longer
existed.

⛔ **The file is NOT readable by a suite author.** It contains the answers; an author who reads it
produces a suite that agrees with this one for reasons that have nothing to do with the protocol. It
is consumed **after** a new suite has run, never before, and the brief lists it as forbidden.

⭐ **And the thing that keeps control B from collapsing into "suite 1 is the oracle": a disagreement
with it is never automatically the new suite's fault.** It is exactly one of three things — the spec
was ambiguous, the peer is wrong, or **one of the two suites is wrong** — and finding out which is
the entire job. **Control B is a comparison set, never an answer key.** The moment it is treated as
an answer key, suite 2 is a copy of suite 1 by a slower route.

⚠ **Control C also just proved it is not decoration.** The normative fixture had a signature vector
built over the wrong message for its entire life, and it was found by **executing** it. Reading a
fixture and running it are different acts. **So even the most independent control gets executed, not
trusted.**

---

### Stage 8 — Run against real peers

**Produces:** verdict documents, one per peer, each recording the peer's **identity** and the
**posture** the run happened in.

**Two inputs that decide the outcome and used to be undeclared:**

1. **The peer set.** Declared as data (`suites/<name>/PEERS.diag`) as a *rule* — roster minus
   exclusions — expanded every run, currently 40 peers. It replaced a hand-typed default list, which
   means **the input that decided every number this repo has published used to be an argument
   somebody typed.**
2. **The posture** — granted scopes, seeded identities, installed handlers. **The founding
   measurement of this seat:** the same tool against the same peer produced **778** checks in one
   posture and **717** in another, with 54 severities moving, every one downward. Those are not a
   better and a worse number; **they are not comparable measurements**, and nothing in either report
   said which was which because there was no field for it.

**Enforcement:** `make peers` · `make peer-identity` · `make lint-peer-diversity` · a suite refuses
to emit a verdict with no posture.

**State: 🔵 BUILT, and one clause is honestly labelled unfinished.**

- The peer set and posture machinery is built and was run — 4 peers. ⚠ **36 declared keystone peers
  remain unrun** because their tree was held; an override exists and was **not** used, because its
  failure mode is a stale report that reads as a result.
- ⛔ **`lint-peer-diversity` clause 2 — "no requirement's evidence resting on one peer or one
  language" — is not implemented and prints that it is not.** The last run is exactly the case it
  would catch: three of the four peers share one generation lineage and returned identical results on
  all 28 requirements. **That is cohort consistency, not independent convergence**, and reading it as
  agreement is the overclaim the ecosystem rules name by name.
- ⚠ **Peer identity resolves for keystone peers only.** For the others the run records a **pin**
  (which bytes) rather than a **certification** (that they were checked), and says so.

---

### Stage 9 — Compare the two suites

**Produces:** a differential joined on **requirement id**, and the list of checks the other
instrument ran that we have no requirement for — which is the next authoring batch's worklist.

**Three rules, and the first is the one that gets broken under pressure:**

1. ⛔ **A disagreement is triaged, never re-run.** A rerun is what you do to a flaky measurement.
   This is two judgements differing, and **the difference is the information.**
2. **Keyed to the requirement id.** *"Suite A passes and suite B fails"* is unanswerable.
   *"We disagree about `ECP-R3`"* has an owner.
3. **Agreement is not coverage.** The last run was `AGREE 45 · DISAGREE 0` — and the other instrument
   was blind on 44 rows, 10 of which were failures nobody else measures.

**Enforcement:** `make differential`.

**State: ✅ SOLID.** It has fired and produced the product this seat exists for: six disagreements
taken apart one input at a time, **every one a real peer defect the other instrument could not see.**

---

### Stage 10 — Triage, route, and ratchet

**Produces:** for each finding, exactly one of — a routed packet to the peer's owner (implementation
bug), a routed question to the architecture seat (specification gap), or a fix here (check bug). Plus
the ratchets moved and whatever the session learned written into the guidance.

⭐ **The restraint rule, which has now paid twice:** a finding is **held unrouted** while the
requirement behind it has an open question. Both times that restraint is what prevented real damage
— once when an obligation was reversed under a result covering 34 peers, once when a ruling landed
the same morning as a run and voided its scoring half. **In both cases the cost was zero because
nothing had been sent.**

**Enforcement:** four down-only ratchets, printed every run — unexecuted requirements · unsplit
requirements · unread sources · checks never re-read against their obligation. **Lowered only by
doing the work, never by editing the number.**

**State: ✅ SOLID.** ⚠ **With one live counterexample kept visible:** a requirement can be
re-authored while the code that measures it is not, and every gate stays green, because **every gate
measures a declaration.** That cost a void measurement and a prediction that could not have fired.
The remedy is a declared column plus a debt ledger — **26 of 28 checks had never been read against
the obligation they measure, now 25** — and the ledger paid for itself inside an hour.

---

## 3. What is actually broken, ranked

| # | Gap | Stage | Why it matters |
|---|---|---|---|
| ~~1~~ | ✅ **CLOSED 2026-09-16** — control-set artifact + gate, shown to catch the real incident | 7 | — |
| **2** | ⛔ **Nothing enforces author separation.** | 4 | The one constraint that makes a second suite worth building, held together by honesty alone |
| **3** | ⛔ **`lint-peer-diversity` clause 2 unimplemented.** | 8 | The last run is the case it would catch; three peers of one lineage read as three confirmations |
| **4** | 🟡 **3 of 50 requirements are in buildable shape.** | 2 | The binding constraint on suite 2's scope. Not fixable by automation |
| **5** | 🟡 **The suite contract is unratified**, by three seats. | 5 | Until then a second suite is portable by assertion |
| ~~6~~ | ✅ **CLOSED 2026-09-16** — the brief now ranks the three and says which validates what | 3 | — |
| **7** | 🟠 **`make help` has drifted** — targets built in the last three sessions are not listed. | — | The documented interface is stale; small, and exactly the class of thing that is never noticed |
| **8** | ⛔ **NEW — run artifacts are overwritten in place.** Re-running a peer destroys the prior measurement's pin. | 8 | The 06:42 peer pins are unrecoverable; they survive only because the control set copied them by hand. **For a seat whose product is comparability, a measurement that cannot be compared to its own predecessor is a real defect** |
| **9** | ⚠ **REFRAMED — a counterpart's tree is dirty most times you look at it.** Three of the four control peers were pinned to uncommitted bytes at run time. | 7/8 | ⭐ **Not fixable and not a blocker: durability comes from REPETITION, not cleanliness.** These verdicts were produced 4× across 3 peer-tree states and did not move. Waiting for a clean pin is waiting forever |
| **10** | ⛔ **NEW — the instrument's own identity was a git string that named the wrong commit and could never be refreshed.** | 5 | Found in the review pass. `suite.version` is half of the dual anchor a published number is accountable to. **Fixed: `suite_source_digest` over the bundled sources.** Third instance in one day of a name standing in for content |

---

## 3a. ⛔⭐ The edge this diagram did not have

```
   upstream specification  ──┐   ← THE ARROW THAT WAS MISSING
                             │     (four revisions in six days; nothing here looked)
                             ▼
   1 pin ──► 2 state ──► 3 chunk ──► 4 author ──► 5 build ──► 6 control
                                                                  │
   10 triage ◄── 9 compare ◄── 8 run ◄───────────────────────────┘
        │
        └──────────────────► back into 1–2          ← the only edge that existed
```

**Stage 10's edge carries what WE learn back into the corpus. There was no edge for what the
SPECIFICATION learns.** Everything below the top is pinned to the thing above it and nothing is
pinned to the top, so the whole chain can drift together and report green at every link — which is
precisely what happened to `ECP-R3`, the control set, and the brief, in that order.

⚠ **The remedy is NOT to chase** (operator direction). It is to make the distance visible: *"our pin
is N revisions behind upstream HEAD"*, printed. **Not built. Named here so the next session does not
have to rediscover it, and so nobody grades stage 1 SOLID again without asking this question.**

---

## 4. What this workflow says to do next, in order

1. ✅ **DONE — the control-set artifact and its gate** (gap 1), populated for all three requirements
   across four peers, all re-measured against HEAD's obligation text.
2. ✅ **DONE — the brief ranks the three** (gap 6): `ECP-R57` validates, `ECP-R3` validates,
   `ECP-R7` observes.
3. ⭐ **NEXT — hand the brief to a fresh author** (stage 4): a context that has not read this
   document, the control set, suite 1, or the run records. **This is the step that has never
   happened and it is the only one that tests the sequence.**
4. **Run stages 8–10 on `ECP-R57` and `ECP-R3`**, compare to the control set, and triage every
   disagreement as one of the three outcomes — **never by re-running it.**
5. Then, and only then, widen the chunk.

⚠ **Step 4 is the real test of this document, and it has not happened.** Everything above is a
sequence that has been walked in pieces, by one seat, on one suite. **It has never been walked end to
end by someone who was not there when it was written** — which is the same unexamined-from-inside
defect this seat was founded on, pointed at its own process.

---

## 5. What this document does NOT decide

- **The requirement format's ratification.** Ours to propose, the architecture seat's to rule.
- **Which peer pairs get run for cross-peer requirements**, how chosen, how often re-chosen. Open,
  unargued, and named as the first hard design question this repo owns.
- **Who is right when two suites disagree.** The architecture seat, by ruling. **This sequence's only
  job is to make a disagreement legible enough to adjudicate.**
- **Whether the peer-set nesting rule can be satisfied at all** when one suite declares the whole
  roster and every possible subset is nested inside it. Raised, deliberately unresolved, **and it
  must not be resolved by quietly shrinking either side to make a gate go green.**
