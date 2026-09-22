# rs-conformance — suite 2

The second independent conformance instrument for entity-core. **Rust, `std` only, zero
dependencies, static musl binary.**

> One suite is one opinion. The value starts at two, and only if the second was built
> independently. **If this suite agrees with suite 1, it is because the protocol said so.**

---

## What it was built from, and what it was not

| Read | Not read |
|---|---|
| `spec-data/entity-core-protocol/v0.8.2.26/` — the pinned text, which is the real source | ⛔ suite 1's source, **any file** |
| `requirements/entity-core-protocol/{ECP-R57,ECP-R3,ECP-R7}.diag` — the three obligation-only files | ⛔ any suite's `items/**` — the probe designs |
| `docs/DESIGN-THE-SUITE-CONTRACT.md` · `docs/BRIEF-SUITE-2.md` | ⛔ `suites/CONTROL-SET.diag` — it contains the answers |
| RFC 8949 (CBOR) · FIPS 180-4 (SHA-256) | ⛔ `entity-core-go`'s `validate-peer` (prohibition 3) |
| `tools/{item,implements,peer-binding,suite-constants}-gate.py` — for **schemas**, never for expected values | ⛔ `docs/STATUS.md`, `docs/status/**`, the other 47 requirement files |

⚠ **One unavoidable exposure, declared.** `CLAUDE.md` → `AGENTS.md` is injected into an agent's
context by the harness before its first turn. Its bring-up table carries some recorded-result
material. It could not be declined. Nothing else on the list was opened.

---

## Why Rust, and why no libraries

**Not Go** — the oracle's language. **Not Python** — suite 1's. `make lint-suite-independence`
enforces it.

**SHA-256 is implemented from FIPS 180-4 and canonical CBOR from RFC 8949 §4.2 + ECF §4.1, in
this tree.** A shared library is a shared bug, and two suites exist precisely not to have one.
Suite 1's discarded Go ancestor signed with the same `crypto/ed25519` as the oracle and the
reference peer, refused every CBOR float, and skipped 20 corpus vectors for reasons that were
about Go rather than about the protocol (`AP-10`).

⛔ **Adding a `[dependencies]` section to `Cargo.toml` is a finding, not a convenience.**

**Both codecs self-test on every invocation** — published SHA-256 vectors including the 1e6-byte
one, and ECF §4.1's own worked map-ordering example (which is **length-first**, RFC 8949 §4.2.3,
not plain bytewise — a text-key-only test provably cannot tell the two apart). A failure exits 2
before a single byte is sent. *A wrong codec and a wrong peer are indistinguishable in a verdict.*

**No Ed25519.** None of the three requirements needs one: §3.2 and §4.2 exempt
`system/protocol/connect` from `author` and `capability`, so every probe here is a hello or a
pre-admission refusal and needs no signature. **When a requirement does need it, it comes from
RFC 8032 and is written here.** This is also why the established-connection posture is not
reachable yet — see below.

---

## Build

```sh
suites/rs-conformance/build.sh          # builds, checks it is static, installs to output/bin/
```

Not built by the repo `Makefile`, and it should not be: that builds exactly one instrument
(suite 1's bundled interpreter) and any other suite is **delivered** as an executable.

**Static musl, because the runner `exec`s the instrument inside each peer's own toolchain image**,
where no interpreter and no particular libc is guaranteed. `build.sh` refuses to install a
dynamically linked binary — that failure would otherwise arrive inside a peer container as an
unexplained empty run rather than as a build error.

The target directory is `output/build/` rather than `suites/rs-conformance/target/`. `build.rs`
legitimately *generates* a file naming the snapshot it derived, and `tools/suite-constants-gate.py`
(D16) walks every `.rs` under `suites/` with no build-artifact exclusion. **No Python suite could
have surfaced that.**

## Run

```sh
output/bin/rs-conformance -addr HOST:PORT -profile core -json-out PATH
output/bin/rs-conformance --list-requirements
make peer-up && make core-go-suite SUITE=rs-conformance
```

Both `-flag` and `--flag` are accepted; the runner slot uses one spelling and the contract
document the other, and refusing one would make the suite un-swappable over a spelling.

---

## The three things this suite is careful about

### 1. The two named failures are never collapsed

§4.11 names **dropping the frame** and **closing with no coded frame** as *"distinct failures
rather than one"*. `src/wire.rs` has a separate `Outcome` variant for each and every result
carries a `failure_mode`. **A suite that lumps them still gets every top-line verdict right** —
which is why it is the error worth guarding, and why the first run is interesting:
`entity-core-go` **silently drops** a wrong-root-type frame and **bare-closes** a mis-hashed root.
Same peer, same class, two different non-conformances, two opposite remedies.

### 2. The negative control has a narrow bar, on purpose

Every probe first sends **the same input with the one thing under test corrected** and requires an
**affirmative 2xx**. Anything else — a 4xx, a close, a silence, an unreadable answer, an
unreachable peer — **voids** the probe, and the row becomes `SKIP` with
`peer_attributable: false`.

⛔ **`any response` is not a control.** A control that accepts any response accepts the exact
refusal that must void the probe, and then a peer that refuses *everything* passes every check in
the suite. Exercised: against a mock that refuses everything, all three rows go `SKIP
control_void`, not `PASS`.

### 3. One fresh connection per probe **and** per control

§4.11 (0.8.2.26) lets a peer bound consecutive pre-admission refusals on one connection as local
policy, and says a check set **MUST NOT** assert that bound or its absence. Reusing a connection
would make later probes measure that policy instead of the row they name, and a peer that had
legitimately hit its bound would be scored as a silent drop.

---

## Posture

**It never emits a verdict without one.** With no `-posture` file it uses its built-in
`pre-handshake-floor` posture and labels it `source: suite-builtin-default`. `-posture-grants`
(what `make peer-up` recorded) is copied into the document verbatim, never re-typed.

The posture block carries a **`not_measured`** list. Today it holds two entries, and the first
matters: **`ECP-R57`'s requirement file says its subject is sent on an ESTABLISHED connection, and
this suite sends it pre-handshake.** The argument that the arm is state-independent is written
down (§6.5 places `Other type?` at the same level as `Root is EXECUTE?`, before any state branch)
— **but an argument is not a measurement**, and the established-posture run is not taken.

---

## Known gaps, stated rather than left to inference

- **The ten declared keystone peers are unrun.** Only `entity-core-go` has been measured. One peer
  establishes no distribution and nothing here is routed as a cohort finding.
- **No `generator` source in `PEERS.diag`.** Not enumerated this session, so declared absent rather
  than guessed at. An unverified peer name in the one artifact whose job is auditability is worse
  than a gap.
- **`ECP-R7` scores nobody** and the scoreable form (a *referenced* entry) is not designed. That is
  legitimate unclaimed work and is not suite 1's.
- **The `ECP-R3` code disagreement is undecided by the only run taken.** `entity-core-go` emits no
  code on that surface at all, so the run distinguishes neither reading. It is decidable only
  against a peer that answers with a code.
