# PROCESS — how this repository works, and why the method is the deliverable

**An instrument is only as good as the argument for trusting it.** Test suites are easy to write and
hard to believe: a check that has never been made to fail, a number produced under preconditions
nobody wrote down, a second opinion that read the first one's answers — each of those produces
output that looks exactly like a measurement. **So the method here is not overhead around the work.
It is most of the work**, and it is published for the same reason the requirements are: you should
be able to check it rather than take our word for it.

This document is the shape of the process. The rules themselves live in
`docs/DISCIPLINE-CHARTER.md`; the procedure for standing up a suite lives in
`docs/WORKFLOW-SUITE-BRINGUP.md`; the structural argument lives in
`docs/MODEL-THE-MEASUREMENT-STACK.md`.

---

## 1. The three prohibitions

Each one is a way of becoming the thing this repository was built to check.

1. **Never ship a peer.** The moment a conformance instrument implements the protocol, it is writing
   its own exam. When a check needs a behaviour no available implementation provides, that is a
   **finding routed to that implementation's owner**, never something built here.
2. **Never author the specification.** We state what the spec requires; we do not decide it. An
   ambiguity goes upstream. *A requirement we invented is a requirement nobody agreed to, and a
   suite that passes it proves nothing.*
3. **Never read another instrument's source while authoring a requirement.** Requirements come from
   the specification. Another oracle is a source of *coverage questions* — *"it tests this; is there
   a requirement for it?"* — and never a source of expected values. **Transcribing it makes us a
   second copy of it**, which costs everything and measures nothing.

## 2. The loop — nothing counts until it has run

> **Author → implement → run → compare → triage → feed back.** Per category, before authoring the
> next one.

This is the rule that cost the most to learn. Fifty requirement files were authored, reviewed and
gated here before a single one was executed; **the first run found a defect in a requirement within
minutes that three review passes had not.** A requirement nobody has run has not been shown to
measure anything, so *"executed by a suite"* is a tracked number, not an assumption.

**Comparison is joined on requirement ids, never on check names.** *"Instrument A passes and
instrument B fails"* is unanswerable. *"We disagree about `ECP-R3`"* is a well-posed question with an
owner.

**And agreement is not coverage.** Every comparison also lists the checks another instrument ran for
which we have no requirement at all. That list — not the agreement — is the next batch's worklist.

## 3. What a disagreement is for

**A disagreement between two instruments is the product, not a defect.** Exactly one of three things
is true, and finding out which is the job:

| | Outcome |
|---|---|
| **Specification gap** | the requirement was ambiguous — it goes upstream and the spec gets refined |
| **Implementation bug** | the peer is wrong — it goes to the peer's owner |
| **Check bug** | one of the instruments is wrong — fix it, in both if the gap is shared |

⛔ **A disagreement is never resolved by re-running it.** A rerun is what you do to a flaky
measurement. Two judgements differing is not flakiness; the difference is the information.

## 4. How a rule gets to exist here — the promotion ladder

**Rules are earned on evidence, never on speculation.**

| | |
|---|---|
| It bit us **once** | an entry in the anti-pattern catalogue, with the incident that earned it |
| Between one and two | a **candidate** — apply it, do not claim it generalizes |
| It bit us a **second time in a different shape** | a ratified **discipline** — and **only with an enforcement point** |

⛔ **A discipline with no enforcement point does not count.** Name the gate, the grep, the lint rule
or the test that fires, or it is advice. A rule added on speculation is removed if it has not earned
itself within a release cycle.

**The feedback edge is not optional.** Every piece of work ends by feeding what it taught back into
the rules **in the same session**. If it did not land in the charter, it did not land.

## 5. Negative controls, everywhere, including on ourselves

> **A check that cannot be made to fail has not been shown to measure anything.**

- **Every requirement carries a negative control** — especially the ones that can never fire against
  a correct implementation.
- **Every gate here ships a `--self-test`** that plants a defect and asserts the gate refuses it. A
  gate whose self-test has never been shown to catch its own real incident is graded as unproven,
  not as working.
- **A verdict is `PASS` only if the conformant arm held *and* the control discriminated.** If the
  control did not discriminate, the result is `INCONCLUSIVE` — never a pass.

## 6. The inputs that decide an outcome are declared as data

Three of the worst measurement failures in this ecosystem were not bugs in any code. They were
**inputs chosen once, by one party, and never written down.**

- **The posture.** A check declares the preconditions it assumes — granted scopes, seeded
  identities, installed handlers — **as data**. A precondition stated only as English inside a skip
  message is not declared. One instrument run against one peer under two postures changed the *size*
  of the check set and moved dozens of severities, all downward, and nothing in either report said
  which was which. **Two runs under different postures are not a better and a worse number — they
  are not comparable measurements.**
- **The peer set.** Membership is a rule (a roster minus declared exclusions), expanded and recorded
  every run, and a verdict records each peer's **identity**, not its name. A pin says *which bytes*;
  a certification says *they were checked*; those are different claims and are reported separately.
- **The obligation.** Every verdict carries the sha256 of the requirement text it was scored
  against. A requirement's text can move twice in one day — ours did — and verdicts recorded either
  side of that are not comparable, however similar they look.

## 7. Ratchets — the numbers that may only go down

Four ledgers are printed on every run, and each one names something **not** established:
requirements no suite has executed · requirements whose obligation and probe are still fused in one
file · material we rely on without having read · checks never re-read against the obligation they
measure.

**They are lowered by doing the work, never by editing the number**, and a build fails if one rises.
They exist because the alternative is a repository whose debts are only visible to whoever last
touched them.

⭐ **Read them as the honest half of every number we publish.** *"25 checks have never been read
against their obligation"* is not a claim that 25 checks are wrong — it is the claim that nothing
here has established which version of the rule they implement, which is a much more useful thing to
know than a coverage percentage.

## 8. Where we are in the refinement, plainly

**This is published early, deliberately.** The instrument is the piece the rest of the architecture
leans on, and getting it examined matters more than getting it finished quietly.

- **The requirement corpus is real and partial** — 50 obligations authored, 15 of the protocol's 98
  core obligations covered. The rest is work, not a blocker.
- **Two suites exist; the second reaches three requirements.** So almost everything is still measured
  one instrument deep, and *one instrument's errors are invisible by construction.*
- **Parts of the process are proven and parts are improvised, and the workflow document grades each
  stage by whether it has ever caught a real defect** — not by how much effort went into it. Two
  stages are graded MISSING in that document right now, and they are named rather than smoothed over.
- **One thing we cannot yet enforce:** independence between suite *authors*. Language, dependency
  and codec independence are gated and have fired. Context independence is not, and the agent tooling
  used to build the second suite breached it in a measurable way, which is written up rather than
  waved off.

> **The finish line is measurable and we have not reached it: a new suite, built independently,
> finds nothing.** Until then, every disagreement is worth more than every agreement, and this
> repository is a work in progress that would rather be checked than admired.
