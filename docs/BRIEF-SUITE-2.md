# BRIEF — building suite 2

**For the session that builds it.** Prepared 2026-09-16 by the session that had just worked on
suite 1, which is exactly why that session did not build this.

---

## 1. Why you exist, in one paragraph

There is one existing conformance tool for this protocol, written in Go by the same people who wrote
the reference implementation. If it has a bug, every implementation gets "fixed" until it matches the
bug, and then the bug is indistinguishable from the protocol. This repo is the second opinion. **One
suite is just our opinion; the value starts at two**, and only if the second was built independently.

**The finish line is a new suite finding nothing.** Until then, every disagreement between two suites
is the product, not a defect.

---

## 2. ⛔ What you MUST NOT read

This is the whole brief. Everything else is detail.

| Do not open | Why |
|---|---|
| `suites/py-prototype/**` — **any file** | suite 1's source. Reading it makes you a second copy of it, and the two suites will then agree for reasons that have nothing to do with the protocol |
| `suites/*/items/**/*.diag` | the **probe designs** — which bytes to send, which answers to accept. the standing rule is *sharing the substrate is fine; sharing ASSERTIONS is not* |
| the 47 requirement files **not** listed in §3 | they still have suite 1's probe design fused inside them (`arm`, `given`, `step`). Opening one hands you suite 1's test |
| `entity-core-go`'s `validate-peer` source | prohibition 3. It is a source of *coverage questions*, never of expected values |
| ⛔⭐ **`suites/CONTROL-SET.diag`** | **it contains the answers.** The expected verdict for every peer on every requirement you are about to implement. Reading it does not help you build a suite — it lets you write one that agrees, which is worth nothing. **It is read by whoever validates your work, after you have run.** |
| ⛔ **`docs/WORKFLOW-SUITE-BRINGUP.md`** and **`docs/status/HANDOFF-*`** | the operator's and validator's documents. They name which requirements are expected to pass, which implementations fail and how, and what the validator will check you against. **Same problem as the line above, in prose.** |
| `docs/STATUS.md`, `docs/status/RUN-*`, `docs/outbox/ROUTING-*` | recorded results. You would be reading the answers with extra steps |

⚠ **If you have already read any of these, say so before you write a line of code.** It is not a
failure and nothing bad happens — **you stop being the author and become the validator**, and
somebody else builds it. **Discovering that afterwards is what costs.** The first attempt at a second
opinion here was thrown away for a subtler version of exactly this.

⛔ **One exposure you cannot decline, and we would rather you name it than assume we know.** If your
tooling injects this repo's operating guide (`CLAUDE.md` → `AGENTS.md`) before your first turn, that
is outside your control and outside ours. **Say so in your first report, as the author of suite 2
did, unprompted.** That file is under a standing rule to carry no recorded results — no verdict, no
peer outcome, no expected value — precisely because it arrives before this brief does. **If you find
one in it, that is a finding about us, and reporting it is worth more than the suite.**

⭐ **This has already gone wrong once here.** Suite 1 was first written in Go, signed with the same
crypto library as the oracle and the reference peer, and agreed with them beautifully — because it
shared their habits. It refused every CBOR float and skipped 20 corpus vectors for reasons that were
about Go, not about the protocol. It was thrown away and rewritten in Python. **That is the failure
mode; it is not hypothetical.**

**If you find yourself needing something from suite 1 — a helper, a trick, a shape — that is a signal
the requirement is underspecified. Say so. That report is worth more than the code.**

---

## 3. ✅ What you MAY read — and it is small on purpose

**Three requirement files.** These are the only ones in `ADR-0003` shape: obligation only, no probe.

```
requirements/entity-core-protocol/ECP-R57.diag   wrong root message type          ⭐ START HERE
requirements/entity-core-protocol/ECP-R3.diag    root entity hash validation
requirements/entity-core-protocol/ECP-R7.diag    included entity hash validation  (observer only)
```

⭐ **They are ranked, and the order is not arbitrary.** Behind this brief there is a set of peers
whose behaviour on these requirements has already been observed, and it is what your work gets
checked against. **You may not see it** — but you should know what it can and cannot detect:

| | |
|---|---|
| **`ECP-R57`** ⭐ | **The best target.** Some peers satisfy it and some do not, **and the ones that do not fail in two different ways that the specification requires be scored separately.** A suite that lumps those two together still gets every top-line verdict right — so this is the requirement most likely to catch a subtle error in your work, which is exactly why it is first. |
| **`ECP-R3`** | Also has peers on both sides. ⛔ **Its file's reading of which error code is required is KNOWN TO BE WRONG — see §3a.** Build it from the specification, not from the file's conclusion. |
| **`ECP-R7`** | **Observer only.** No peer produces a verdict. See the caveat below. |

**Plus the specification**, which is the real source: `spec-data/entity-core-protocol/v0.8.2.26/`.
Requirements come from the **spec**. A requirement file is a neutral statement *about* the spec and a
reading you may disagree with — **disagreeing with it on contact is a valid output.**

### 3a. ⛔ Two things about these files that we know are wrong, told to you up front

**Not a disclaimer.** Every conformance seat that has ever shipped a bad check shipped it because
the author trusted a written-down conclusion over the normative text. These two are the ones we
have found; there are probably others, and **finding one is a better day's work than a passing
check.**

1. ⛔⭐ **`ECP-R3`'s reading argues that the specification pins NO error code for this cause. That
   argument is false against the PINNED snapshot you are given** — `v0.8.2.26` §6.5's dispatch
   chain reads *"Validate root entity hash → 400 `hash_mismatch`, coded frame; MAY then close"*, and
   `ECP-R3` cites §6.5 in its own `spec` field. §4.11 in the same snapshot says *"a cause absent from
   this table is a cause whose code is assigned by its own section."*
   ⇒ **Read §6.5, §4.11 and §1.8 yourself and reach your own conclusion.** If you conclude the file
   is wrong, you are right, and **say so** — it is the finding, not a nuisance.
   ⚠ **This paragraph itself was wrong until 2026-09-17.** It said the code was added *"in a version
   this repo has not yet pinned"* — i.e. that the spec had moved under us. **The first author to
   receive this brief opened §6.5 and showed it had been in the pinned text all along.** Two of our
   sessions and three review passes had not. **That is what the second opinion is for, and it
   arrived before their first check ran.**
2. ⚠ **`ECP-R57` rejects one particular error code on the grounds that its scope is limited to a
   narrow case. That scope was later WIDENED.** We believe R57's conclusion survives — for a
   different reason stated in the same sentence — but **the reason it gives you is stale.** Check
   the argument rather than inheriting it.

⚠ **Both of these come from the same cause, and it is worth knowing because it will affect you
too:** the specification is not a frozen input. It moved **four times in six days**, and our pinned
snapshot (`v0.8.2.26`) is **three revisions behind** the upstream document as of 2026-09-16.

**Build against the pinned snapshot anyway** — a measurement whose input nobody pinned is not a
measurement, and chasing a moving document is how nothing ever gets finished. But **record which
snapshot you built against in every verdict**, and treat *"the pinned text and the requirement file
disagree"* as an expected output rather than a surprise.

**Plus** `docs/DESIGN-THE-SUITE-CONTRACT.md` (how you are invoked, what you emit) and this file.

⚠ **`ECP-R7` is WITNESS-ONLY and cannot be scored.** `0.8.2.26` ruled its input mechanism-shaped: a
check MUST NOT assert a refusal on an unreferenced included entry. Implement it to **observe and
record**, never to produce a verdict. Its `scope_correction` block explains, and the scoreable form
(a *referenced* entry) is not designed yet — designing it is legitimate work and is not suite 1's.

⇒ **Realistically you are building two scoreable checks and one observer.** That is deliberate. A
suite claiming broad coverage on day one is a suite that is transcribing.

⚠ **One thing about those peers that will confuse you if nobody says it.** Some of them are being
actively worked on in their own repository, with uncommitted changes. **A peer's behaviour can change
between two runs on the same commit.** If a result moves under you, that is not necessarily your bug —
record which peer, and what it did, and say when you ran it.

---

## 4. Language and shape

- ⛔ **Not Go** — the oracle's language. ⛔ **Not Python** — suite 1's.
- ⛔ **No crypto or CBOR library.** Ed25519 from RFC 8032, canonical CBOR from RFC 8949. **A shared
  library is a shared bug**, and two suites exist precisely not to have one.
- ✅ **Anything else.** `make lint-suite-independence` enforces the language rule.

**Suggested: Rust, static (musl).** Not a requirement — the reason is practical. The instrument is
`exec`'d **inside each implementation's own container**, where no interpreter is guaranteed to exist.
Suite 1 solves that by bundling an entire pinned CPython. A static binary just runs. **If you pick
something else, solve that problem before you write a check** — it is the one that sank the first
attempt at packaging.

**Invocation you must accept** (the standard slot every runner uses):

```
<binary> -addr HOST:PORT -profile core -json-out PATH
```

**Where your work plugs in** — built 2026-09-16, and until then there was no slot at all:

```
output/bin/<your-suite-name>        your executable (+ output/bin/<name>.d if it needs a bundle dir)
suites/<your-suite-name>/PEERS.diag      the peer set you declare — a RULE, not a hand-typed list
suites/<your-suite-name>/IMPLEMENTS      the requirement ids you claim, one per line

make require-suite SUITE=<your-suite-name>     tells you which of the three is still missing
make core-go-suite SUITE=<your-suite-name>     runs it (after make peer-up)
make keystone-suite / generator-suite SUITE=…  the other two peer sources
```

⚠ **Your suite is not built by this repo's Makefile** and should not try to be. It builds exactly
one instrument — suite 1's bundled interpreter — and **you deliver an executable.** Build it however
your language builds things.

---

## 5. What a check has to have, or it does not count

**Every check needs a negative control that can be made to fail.** *A check that cannot be made to
fail has not been shown to measure anything.* Concretely: for every probe, send the **same input with
the one thing under test corrected**, and confirm the peer answers. Without it, a peer that refuses
*everything* passes your probe.

⚠ Suite 1 got this wrong inside a control on 2026-09-16 — the control accepted **any** response,
including the exact refusal its own design said must void the probe. **The control is where to be
paranoid.**

**Declare your preconditions as data**, not as English in a skip message. What grants, what identities,
what handlers. Every verdict records the posture it ran in. This repo was founded on a measurement
where the same tool against the same peer produced **778 checks** in one posture and **717** in
another, with 54 severities moving — and nothing in either report said which was which.

**A skip counts as a failure.** Say *"could not look"* and why; never let it read as a pass.

---

## 6. Which implementations you run against

**Suite 1 declares the whole roster** (`suites/py-prototype/PEERS.diag`), which creates a problem you
should not solve silently: `ADR-0003` §7.3 refuses two suites whose peer sets are identical or nested,
and every possible set of yours is nested inside the roster.

⛔ **That is unresolved and it is not yours to decide alone. Raise it; do not quietly shrink
either side to make a gate go green.**

⚠ **Earlier this section told you to go read the write-up inside suite 1's `PEERS.diag`, which §2
forbids you to open. That was a real contradiction in this brief** — reported by the first author to
receive it, who complied with §2 and said so. **§2 wins.** You do not need that write-up: the
condition is that suite 1 declares the whole roster, so every set of yours is nested in it. Declare
what you can actually reach, say why, and file the question.

⚠ **Running against `entity-core-keystone`'s peers needs their tree free** — their census refuses to
start while another container holds it. **Do not set `CENSUS_IGNORE_HOLDERS=1`**: their own message
says the report write then fails silently while the tool exits 0.

---

## 7. What to report back, and what is genuinely valuable

In rough order of value:

1. ⭐⭐ **"I could not tell what this requirement wanted."** The most valuable sentence this repo
   produces. It is never a failure to report it, and sitting on it to look competent wastes the
   entire exercise.
2. ⭐ **A disagreement with suite 1.** Exactly one of three things is true and finding out which is
   the job: the spec was ambiguous · the implementation is wrong · one of the two suites is wrong.
   **Never resolve a disagreement by re-running it.** A rerun is for a flaky measurement; this is two
   judgements differing, and the difference is the information.
3. **A place the requirement file and the spec disagree.** The spec wins; the file gets fixed.
4. Working checks.

**Report disagreements keyed to the requirement id.** *"Suite A passes and suite B fails"* is
unanswerable; *"we disagree about `ECP-R3`"* has an owner.

---

## 8. ⚠ Before you author anything: read the inbox

**Not optional, and it has now cost this repo twice in two days.** Sibling repos deliver by committing
a document to their own tree — there is no notification and nothing here pulls. On 2026-09-16 a rule
was re-authored and run against four implementations while the ruling that invalidated it had been
sitting in `entity-system-architecture`'s tree since 09:25 **that morning**.

```
make inbox
```

It lists every sibling `ROUTING-*` whose **`To:`** names this repo, and which of them are on no
tracker. ⚠ **It counts packets, not asks** — it says `asks: unread` on every row and means it. Open
the ones it names.

⛔ **Do not substitute a grep for it.** A grep on `ROUTING-2026-09-16-b` matches a packet in *any*
repo with that date and letter, including ours; `<date>-<letter>` is unique to one repo on one day,
which is not unique. That exact mistake produced a false *"already handled"* on 2026-09-16.

---

## 9. Where the real state is — **and it is not yours to read**

⛔ **For the operator and the validator, not for the author.** `docs/STATUS.md` and the run records
carry recorded results, which is why §2 forbids them to you. **This section exists so that nobody
sends you there believing it is background reading** — an earlier version of this brief did exactly
that, pointing its own reader into a file it forbids two pages earlier.

⚠ **If you need a fact about the state of this repo in order to build, ask for it.** A fact handed
over deliberately, with the answer withheld, costs nothing. A fact you go and find for yourself
usually arrives attached to the answer.

**Honest scale:** the protocol has ~98 core obligations. 15 have a requirement written. 3 are in a
shape you can build against. **You are not behind — the corpus is.**
