# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

**The first public release of this repository.** Nothing below has been published before, so all
of it is new to anyone outside it.

**Breaking:** no — this is the first public release. There is no earlier version of this repository
for anything to have been built against, and nothing that was public has been withdrawn. The answer
is written down rather than left to be inferred, because *"nothing can break when nothing exists
yet"* is the one release where the question never gets asked, and it is only worth anything if the
surface it is about has been named. It has: see **The public surface** in `AGENTS.md`. The short
form is that **a requirement id is the commitment** — allocated once, never renumbered, never
reused — and that the suite invocation contract is **declared and not yet ratified**, which is
stated as a limitation and not as a promise.

**What a version number here does not mean.** It does not track the specification's version, and
it is not a claim about how much of the protocol is covered. The coverage figures and the four
ratchets are printed on every run and move independently of it; a release that lowers one of them
has not broken anything. Each suite carries its own package version for its own lifecycle, declared
at the repository root so the difference is a statement rather than a discrepancy.

### Added

- **`requirements/` — the deliverable.** 50 requirement files over `entity-core-protocol`, each one
  independently failable, authored from the pinned specification text and stating both arms: what a
  conformant peer does and what a non-conformant one does. Every file carries a negative control,
  because a check that cannot be made to fail has not been shown to measure anything.
- **`spec-data/` — pinned specification snapshots**, sha256 per document, copied in and never
  edited. A requirement names the snapshot it was authored against, so a moving upstream makes
  re-reading a worklist with a number on it instead of a silent re-pointing.
- **Two independent suites.** `suites/py-prototype` (Python, standard library only) and
  `suites/rs-conformance` (Rust, `std` only, zero dependencies, static binary). They share no code,
  no codec, no cryptography and no language; the second was built by an author who had not read the
  first. Cryptography and canonical encoding are written from the RFCs rather than taken from a
  library the cohort already shares.
- **The requirement/item split.** A requirement is the obligation; an item is one suite's probe of
  it. Two suites join on requirement ids and share no assertions — shared assertions are shared
  bugs, which is the one thing two instruments exist not to have.
- **`make differential`** — joins runs from any two instruments by requirement id, and lists every
  check the reference oracle ran for which this repo has no requirement at all.
- **A declared peer set.** Membership is a rule, not a hand-typed list; a verdict records a peer's
  identity and whether it is certified by a run contract or merely pinned.
- **Declared posture.** Every verdict records the preconditions the run assumed, as data. Two runs
  under different postures are not a better and a worse number — they are not comparable
  measurements.
- **Four down-only ratchets**, printed every run: requirements no suite has executed · requirements
  whose obligation and probe are still fused · material relied on but unread · checks never re-read
  against the obligation they measure. They are lowered by doing the work, never by editing the
  number.
- **`docs/CLI.md`** — the build, run and comparison interface.
- **`make fmt`** — a Tier-1 verb that reformats nothing and prints the complete list of why. It
  says so out loud rather than exiting quietly, because a verb that prints nothing and succeeds
  cannot be told apart from one that ran and found no work.
- **`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `SECURITY.md`** — how to propose a change and the
  sign-off it needs, what is expected of people here, and how to report a security problem
  privately instead of in a public issue. They had never been written in this repository, which
  nothing noticed until the first release was prepared.
- **The repository states its own public surface** — what a version number here is a promise about
  and what it is not, in `AGENTS.md`. Without it, "breaking" has no referent.

### Changed

- **`AGENTS.md` is now orientation, and what this project has learned moved to `docs/agents/memory/`**
  behind an index, read on demand rather than in full. The file had grown past the point where
  every session pays to load it; the content was moved rather than cut.
- **Routing documents sent to another repository now live in `docs/outbox/`.** Discovery used to
  mean grepping filenames for your own name, which silently misses a document that named you
  differently and never finds one where you are only copied in.

- `requirements/<spec>/` and `spec-data/<spec>/` now mirror each other name-for-name, keyed to the
  specification's own name. The previous abbreviation collided with an unrelated term of art in the
  protocol and survived four working sessions because no gate can see a name; the mirror is now
  enforced by a gate.

### Fixed

- **The instrument that enumerates inbound documents was scanning one directory and reporting a
  clean result over the other.** When a counterpart moved their sent documents to a new location,
  the scan returned "none addressed to us" — which is byte-identical to a genuine clean scan — while
  that counterpart held 130. It now reads both locations, names any counterpart it could not scan
  rather than counting them as zero, and takes a list of search roots instead of one. Its self-test
  now plants a document in each location; every existing control had held, because the addressee
  parser was never the broken half.
- The canonical-CBOR map-key ordering rule in one of the two encoders (length-first, RFC 8949
  §4.2.3, not bytewise §4.2.1). Latent — every key in the corpus is text, where the two orderings
  provably coincide — and found by comparing the two implementations rather than by either one's
  own tests.
- An encoding vector in the specification's normative corpus that had been built over the wrong
  message since it was written, found by executing the corpus rather than reading it, and routed
  upstream.
