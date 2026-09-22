# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

### Changed

- `requirements/<spec>/` and `spec-data/<spec>/` now mirror each other name-for-name, keyed to the
  specification's own name. The previous abbreviation collided with an unrelated term of art in the
  protocol and survived four working sessions because no gate can see a name; the mirror is now
  enforced by a gate.

### Fixed

- The canonical-CBOR map-key ordering rule in one of the two encoders (length-first, RFC 8949
  §4.2.3, not bytewise §4.2.1). Latent — every key in the corpus is text, where the two orderings
  provably coincide — and found by comparing the two implementations rather than by either one's
  own tests.
- An encoding vector in the specification's normative corpus that had been built over the wrong
  message since it was written, found by executing the corpus rather than reading it, and routed
  upstream.
