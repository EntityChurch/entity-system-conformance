# entity-system-conformance

**The independent conformance instrument for the Entity Core Protocol** — a neutral,
language-agnostic statement of what the protocol requires, and **as many independently built test
suites over it as we care to build.**

This repo exists to answer one question that nothing else in the ecosystem can:

> **When a test says a peer is wrong — is the specification wrong, is the implementation wrong, or
> is the test wrong?**

Exactly one of the three is true every time, which is what makes the question decidable. But a
single oracle cannot tell you which, because every check it runs is scored by the same judgement
that wrote the check — **its own errors are invisible by construction.** And an oracle's bug does
not stay in the oracle: every implementation is fixed until it passes, so the bug becomes the
observed behaviour of the whole cohort, and then it is indistinguishable from the protocol.

**The thing this exists to prevent is one implementation's mistakes being canonicalized as the
standard.**

---

## The shape

```
requirements/   ← THE DELIVERABLE. What the protocol requires, in neutral language,
                  keyed to <PREFIX>-R<n> requirement ids. Not code, not a test.
suites/         ← N independent implementations of those requirements. Different
                  languages, different authors, built without reading each other.
spec-data/      ← the pinned spec snapshot each requirement was authored against,
                  sha256 per document. Copied in, never edited.
```

**`requirements/` and `suites/` being separate directories is the whole design.** One neutral
statement of an obligation; many independent probes of it. A requirement says *what must hold*; a
suite's item says *how this instrument goes and looks*. The two are separate objects because two
suites that shared a probe would share its bugs, and not sharing bugs is the entire reason there
are two.

Each suite declares which requirements it implements, so coverage is reported **jointly** — *"suite
A reaches 28 of 50, suite B reaches 3, together 28"* — and a disagreement between them is keyed to
a requirement id rather than to either suite's internal check names. *"Instrument A passes and
instrument B fails"* is unanswerable. *"We disagree about `ECP-R3`"* has an owner.

## How a disagreement is used

**A disagreement between two instruments is the product, not a defect.** When two suites differ on
one peer, exactly one of three things is true, and finding out which is the work:

| | Outcome |
|---|---|
| **Specification gap** | the requirement was ambiguous — it goes upstream, and the spec gets refined |
| **Implementation bug** | the peer is wrong — it goes to the peer's owner |
| **Check bug** | one of the two suites is wrong — fix it, in both if the gap is shared |

**A disagreement is never resolved by re-running it.** A rerun is what you do to a flaky
measurement. This is not a flaky measurement; it is two judgements differing, and the difference is
the information.

## Where it stands

**Two suites exist. The instrument has been run on real peers, and every number below is the
measured one.**

| | |
|---|---|
| Requirements authored | **50** — 15 binding a floor row, 8 awaiting a floor-row split, 27 binding a body obligation the floor does not list |
| Of the core floor's 98 obligations | **15 covered.** The rest is authored work not yet done |
| Executed against real peers by a suite | **28 of 50** — a requirement nobody has run has not been shown to measure anything |
| Suites | **2** — `py-prototype` (Python, stdlib only) and `rs-conformance` (Rust, `std` only, zero dependencies) |
| Spec snapshot pinned | `entity-core-protocol/v0.8.2.26`, behind a moving upstream — deliberately, and the gap is printed every run |

**The two suites share no code, no codec, no cryptography and no language**, and the second was
built by an author who had not read the first. Where they agree, it is because the requirement said
so. **Where they disagree is where the value is**, and the first thing the second suite did was
find a defect in a requirement the first had been running for days.

Four down-only ratchets are printed on every run and say what is *not* established: requirements no
suite has executed · requirements whose obligation and probe are still fused in one file · material
this repo relies on without having read · checks never re-read against the obligation they measure.
**They are lowered by doing the work, never by editing the number.**

## The method is most of the deliverable

**A test suite is easy to write and hard to believe.** A check that has never been made to fail, a
number produced under preconditions nobody wrote down, a second opinion that read the first one's
answers — each of those produces output indistinguishable from a measurement. So the process here is
not overhead around the work, and it publishes for the same reason the requirements do: **so you can
check it instead of taking our word for it.**

- **Every requirement carries a negative control**, and every gate ships a self-test that plants a
  defect and asserts the gate refuses it. *A check that cannot be made to fail has not been shown to
  measure anything.*
- **The inputs that decide an outcome are declared as data** — the posture a run assumed, the peer
  set it ran against, and the sha256 of the obligation text each verdict scored. Every one of those
  was, somewhere in this ecosystem, an input chosen once by one party and never written down.
- **A rule gets to exist here only after it has bitten twice, and only with an enforcement point.**
  Speculative rules are removed if they have not earned themselves.
- **Four ratchets are printed on every run and may only go down.** Each one names something *not*
  established, which is the honest half of every number here.

`docs/PROCESS.md` is the whole of it; `docs/DISCIPLINE-CHARTER.md` is the rules themselves.

## Published early, on purpose

**This is not a finished instrument and nothing here pretends otherwise.** It is published now
because it is the piece the rest of the architecture leans on, and being examined is worth more than
being finished quietly. The workflow document grades each stage of its own process by whether that
stage has ever caught a real defect — two are graded MISSING today, and they are named rather than
smoothed over. **Where a claim here is unverified, it says so.**

## What this repo never does

- **It never ships a peer.** The moment it does, it is writing its own exam. A behaviour no
  available peer provides is a **finding routed to that peer's owner**, not a build task here.
- **It never authors the specification.** It states what the spec requires; it does not decide it.
  An ambiguity is routed upstream. A requirement invented here is a requirement nobody agreed to,
  and a suite that passes it proves nothing.
- **It never transcribes another instrument.** Requirements come from the specification text. A
  reference oracle is a source of *coverage questions* — *"it tests this; is there a requirement for
  it?"* — and never a source of expected values.
- **It is not the only scorer.** The existing reference oracle stays, permanently. Two instruments
  are worth their cost only if both run and disagreements are adjudicated by a third party.

## Reading order

| | |
|---|---|
| `docs/PROCESS.md` | how this repository works, and where the work has actually got to |
| `requirements/README.md` | the deliverable — what a requirement file carries and why |
| `docs/DESIGN-THE-REQUIREMENT-FORMAT.md` | how one is written |
| `docs/DESIGN-THE-SUITE-CONTRACT.md` | how a suite is invoked and what it emits |
| `docs/MODEL-THE-MEASUREMENT-STACK.md` | who measures whom, and where the regress actually stops |
| `docs/WORKFLOW-SUITE-BRINGUP.md` | standing up a new suite, end to end |
| `docs/CLI.md` | the `make` targets — build, test, run, compare |
| `docs/STATUS.md` | where the work is now |

## Build

The host needs **`make`, `podman` and `python3`** — nothing else, and nothing is installed on it.

```
make check      # build + test + lint
make build      # suite 1 -> output/bin/py-prototype (pinned interpreter, bundled)
make test       # the codec against the specification's own vector corpus; Ed25519 against RFC 8032
```

`docs/CLI.md` has the run path: pointing a suite at peers, and joining two instruments' results by
requirement id.

**Licence:** Apache-2.0 (`LICENSE`) for this repository's own work — the requirement corpus, the
suites and the tooling. Contributions carry a DCO sign-off.

⚠ **`spec-data/` is vendored, not ours.** It holds unmodified copies of the protocol specification,
pinned so that every requirement can name the exact text it was read from. That text is another
project's work under its own terms — the upstream licence files and a `PROVENANCE.md` sit beside it,
and the authoritative version is upstream, not here.
