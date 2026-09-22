# DESIGN — the requirement format

**Status:** first cut, written by the architecture seat during bring-up. **Not ratified.** The first
job of this repo's agent is to disagree with it on contact with real requirements.
**Depends on:** the measured export of the reference oracle's check set — *what surface has been
thought about* — which is the worklist this format was designed against.

---

## 0. What a requirement file is, and what it is not

**A requirement is one independently failable obligation of the protocol, stated so that someone who
has never seen the reference oracle can implement a check for it.**

| It is | It is not |
|---|---|
| a statement of what the spec requires | a description of what the oracle does |
| neutral — no language, no framework, no API | a test in a language |
| the shared thing N suites implement | the implementation itself |

⛔ **Authored from the specification. Never transcribed from the oracle's source.** The oracle is a
source of *coverage questions* — *"it tests this; is there a requirement for it?"* — and never a
source of expected values. A transcription is a second copy of the first oracle, which costs
everything and measures nothing.

---

## 1. Do not design this from scratch — it mostly exists

`entity-system-generator` has a **working, proven** declarative check format in
`extension-contracts/*/checks/*.toml`, with a schema at `gates/ext-checks/schema.py`. **Read those
five files first.** They already carry: the requirement id, spec sections, the snapshot, the MUST
level, the surface driven, a `reading` that quotes and interprets the normative text, the wire types
sent **with who defines each**, ordered steps with captures, assertions each with a `why`, and both
arms.

**What this document adds to it is four deltas** (§4), all additions rather than replacements.

**And the id vocabulary is not being invented either.** `SPECIFICATION-FORMAT` §8.5a allocates
`<PREFIX>-R<n>`, and the oracle's own citations *already* carry `SUBJECT-CONDITION-N` ids in several
core categories — `PEER-CANON-1`, `PEER-MUT-2`, `COMPOSITION-1`, `PEER-PATTERN-2`,
`AGILITY-CANONICAL-1`. **Where an id already exists in the spec, adopt it. Never mint a second name
for a requirement that has one.**

---

## 2. The shape, with a real requirement

Modelled on `resource_bounds`, a fully-resolved core category — three checks, floor MUSTs, and one
SHOULD, which is exactly the mix that exercises the format.

```toml
[requirement]
id        = "RB-R1"
title     = "An over-limit inbound payload is refused with 413 payload_too_large, and the peer keeps serving"
spec      = "ENTITY-CORE-PROTOCOL §4.10(a)"
snapshot  = "core-0.8.2.21"
level     = "MUST"
profile   = ["core"]
surface   = "wire"          # wire | host-seam | offline | cross-peer
status    = "draft"         # draft | reviewed | ratified

reading = """
§4.10(a): the peer MUST enforce a finite maximum inbound envelope/payload size and reject
over-limit input with `413 payload_too_large` while CONTINUING TO SERVE. The limit VALUE is
impl-defined with a safe default (16 MiB recommended, non-normative); ENFORCEMENT is the floor.
So this requirement has three separable obligations and they fail independently:
  (a) an over-limit payload is refused rather than accepted or truncated;
  (b) the refusal carries status 413 and code `payload_too_large` -- the CODE, not just the status;
  (c) the peer is still answering afterwards.
A peer that closes the connection on over-limit input satisfies (a) and fails (c).
"""

# ── PRECONDITIONS AS DATA. The founding rule of this repo (AGENTS.md). ──
[requirement.preconditions]
grants          = ["system/peer/*:read"]
declared_limits = ["max_payload"]   # the peer must DECLARE its limit or this is unmeasurable
handlers        = []
identities      = ["caller"]

# ── THE ENUMERATED DOMAIN. See §4 delta 2. ──
# Absent = the requirement is scalar. Present = it MUST be exercised once per member.
# [requirement.domain]
# axis    = "content_hash_format"
# members = ["sha256", "sha384"]

[[requirement.arm]]
name     = "refused"
given    = "a payload one byte over the peer's declared max_payload"
expect   = { status = 413, code = "payload_too_large" }
why      = "§4.10(a)'s MUST. The code is asserted, not only the status -- a 413 with the wrong code is a different failure."

[[requirement.arm]]
name     = "still-serving"
given    = "any valid request issued after the refusal, on the same connection"
expect   = { status = 200 }
why      = "keeps-serving is half the MUST and the half a naive implementation fails."

# ── NEGATIVE CONTROL. Mandatory. A check that cannot fail measures nothing. ──
[[requirement.arm]]
name     = "control"
given    = "a payload one byte UNDER max_payload"
expect   = { status = 200 }
why      = "anti-vacuity: proves the refusal arm is discriminating on SIZE and not on the request being malformed."

[requirement.notes]
peer_attributable = true
oracle_check      = "resource_bounds/r1_payload_over_limit"   # provenance only, NEVER the authority
```

**`oracle_check` is a cross-reference for differential runs. It is not the source of the
requirement and must never be read as one.** If it is the only thing that justifies a line in
`reading`, the requirement was transcribed and should be rewritten from the spec.

---

## 3. `level` and what a suite does with it

| `level` | A suite must | A failure is |
|---|---|---|
| `MUST` | run it | a conformance failure |
| `SHOULD` | run it | a **WARN**, never a gate |
| `MAY` | may run it | informational |
| `unreachable` | **declare it and not run it** | — |

**`unreachable` is a real state and it is declared, never silent.** A rule with no peer-observable
surface (`GUIDE-CONFORMANCE` §5.2a) is gated by a **pinned-input vector** — a shared row file of
authored inputs and expected outputs that each implementation runs in its own suite, where *the
crossing is the shared file, not a live peer*. Record it as `unreachable` with the vector named.
**A blank is indistinguishable from "nobody looked," which is the ambiguity this whole repo exists
to remove.**

---

## 4. The four deltas over the generation seat's format

### Delta 1 — preconditions as data

The founding rule. Grants, identities, installed handlers, declared limits — **machine-readable**. A
precondition living in English inside a skip message is not declared, and a run that cannot state
its posture cannot be compared to any other run.

### Delta 2 — a requirement maps to a DECLARATION SITE, and may carry an enumerated domain

**From the export (§1 there): the register counts 201 core declarations; the matrix counts 778
executed checks.** The gap is parameterization — four declarations in `typesystem.go` execute ~108
times against the 53-type floor.

> **A parameterized requirement is ONE requirement with an enumerated domain**, and the domain is
> part of the requirement. `[requirement.domain]` names the axis and its members; **coverage means
> once per member.**

This is `GUIDE-CONFORMANCE` §5.2b arriving from the other side: *a rule enumerating N callsites is
covered only when exercised per callsite; one probe against one arm is a sample, not coverage.*
Making the domain explicit is what stops a suite reporting `1/1` where the truth is `1/53`.

### Delta 3 — core-tier surfaces, not only handler-face

All five prototype checks drive an installed extension handler. Core requirements also need:
`wire` (over the transport against a running peer) · `offline` (a fixture corpus, no peer) ·
`host-seam` (the in-process API, driven by the peer's own harness) · `cross-peer` (**two peers — see
delta 4**).

### Delta 4 — `cross-peer` requirements name a PAIR, and never a language

> **A cross-peer requirement MUST NOT fix the implementation of the counterparty.** The pair is a
> **parameter** of the run. The verdict records which two peers produced the result.

**The reason, and it is the sharpest thing in this document.** The reference oracle's `origination`
checks dial a second peer, and that peer is always the same implementation as the oracle. A defect
on the privileged side is not found — **it is propagated**: every other peer is adjusted until it
interoperates, at which point the defect *is* the cohort's observed behaviour, and observed behaviour
is what everybody reads the spec against. **That is how an implementation bug becomes the protocol,
with the check that should have caught it acting as the vector.**

There is no scarcity of counterparties — 46 peers at 0-FAIL across dozens of languages. There was
only never a reason to vary one.

---

## 5. Rules for authoring

1. **One independently failable obligation per requirement.** If a conversion produces something
   that is really two, **that is a finding to file**, not something to split quietly — the spec
   said one thing and meant two, and that is worth knowing upstream.
2. **Every requirement has a negative control.** Especially the ones that can never fire against a
   correct implementation. *A check that cannot be made to fail has not been shown to measure
   anything.*
3. **Assert the code, not just the status.** Most real interop bugs are accepting invalid input,
   not rejecting valid input — the pre-split archive's `CONFORMANCE-PROPOSAL.md` found this in
   Python↔Rust interop and it has held ever since.
4. **Apply the attribution test:** *could a sibling implementation ship none of this rule and the
   row not move?* If so it is a **self-check** — legitimate, kept, and **never reported as a peer
   result**.
5. **`reading` argues the interpretation; it does not restate the clause.** It is where the next
   person finds out *why* the requirement was read this way, and it is the first thing arch looks
   at when a suite disagrees with the oracle.
6. **Stale citation ≠ missing requirement.** When a citation does not resolve, check whether it
   points into a retired version scheme before concluding the requirement is unwritten. **Measured
   twice already:** `format_agility`'s seven unresolved rows all cite `v7.66`, and the core spec
   carries a `v7.75` retirement clock in the same retired scheme.

---

## 6. Open — the agent picking this up should push back on these

1. **TOML or JSON?** TOML for authoring (the prototype is TOML and `reading` wants multi-line
   strings); a generated JSON projection for suites to consume is probably right, but that is a
   guess.
2. **Is `[[requirement.arm]]` expressive enough for multi-step setup?** The prototype has a
   separate `[[check.step]]` sequence with captures. Merging the two is unresolved and this document
   ducks it.
3. **Where does the id allocation live** so two authors cannot collide?
4. **How does a requirement record that the spec is unclear** rather than silently picking a
   reading? *A `disputed` status with the question attached is probably better than a confident
   requirement nobody can defend* — and shipping it disputed is the behaviour we want.
