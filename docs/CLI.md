# CLI — the make targets and the suite interface

**`make` is the door.** The host needs `make`, `podman` and `python3` (≥ 3.11, standard library
only). Nothing is installed on the host; every build and every run happens in a container or in a
pinned, bundled interpreter. `make help` prints this list from the Makefile itself, which is the
copy that cannot go stale.

Targets are container-default. Where a `-native` variant exists it runs the same work on the host's
own toolchain, which is faster and less reproducible — the container answer is the one to quote.

---

## 1. Build, test, lint

| Target | What it does |
|---|---|
| `make check` | `build` + `test` + `lint`. The single verb to run before believing anything |
| `make build` | builds **suite 1** (`py-prototype`) to `output/bin/py-prototype` plus its bundle directory |
| `make test` | runs suite 1's codec against the specification's own encoding-vector corpus, and its Ed25519 against RFC 8032's test vectors, inside the pinned interpreter |
| `make lint` | the gate family below, in a pinned container |
| `make lint-native` | the same on the host's `python3` (unpinned interpreter version) |
| `make fmt` | **reformats nothing, and prints the complete list of why.** There is no formatter in this repository |
| `make clean` | removes `output/` |

⚠ **The first `make build` on a fresh clone reaches the network**, once: it fetches the pinned
standalone interpreter and the pinned base image, and caches both under `output/cache/`. Every
later build is offline. The interpreter is pinned to `x86_64-unknown-linux-musl`; on another
architecture, override `PYRT_URL`.

**On `fmt` being empty.** It is a real answer rather than a stub, and it says so out loud instead of
exiting quietly — a verb that prints nothing and succeeds cannot be told apart from one that ran
and found no work. Suite 1 is standard-library-only by rule, so a formatter would be the one shared
dependency the suite exists not to have; any other suite is delivered rather than built here and is
its author's to format; and the requirement corpus is **canonical CBOR, which is gated rather than
formatted** — re-encoding those files would move the obligation digests that recorded verdicts were
scored against.

⛔ **`build` knows exactly one suite.** A suite that is not suite 1 is **delivered, not built here**:
drop its executable at `output/bin/<name>` (plus `output/bin/<name>.d/` if it needs a bundle
directory — a static binary does not) and declare `suites/<name>/PEERS.diag` and
`suites/<name>/IMPLEMENTS`. **`make require-suite SUITE=<name>`** names which of the three is
missing, rather than failing as a broken build.

### Why suite 1 ships a bundled interpreter

The standardized ways to run an instrument against a peer execute it **inside that peer's own
toolchain image**, and no interpreter is common to those images. `make build` assembles a pinned,
sha256-checked standalone CPython and a musl loader beside the suite's sources, started through the
loader so the image's own libc is never consulted. A suite in a compiled language ships one static
binary and needs none of this.

## 2. The run path — `SUITE=<name>`

Every run target takes `SUITE=<name>`, defaulting to `py-prototype`. **No recipe on the run path
names a suite literally**; a lint gate holds that open so a second suite has somewhere to plug in.

| Target | Drives |
|---|---|
| `make keystone-suite SUITE=<name>` | the suite against the generated peer cohort, through that project's census probe slot |
| `make generator-suite SUITE=<name>` | the suite against composed peers, through the host-launch client slot |
| `make core-go-suite SUITE=<name>` | the suite against the reference implementation's peer (run `make peer-up` first) |
| `make keystone-s1` · `generator-s1` · `core-go-s1` | the three above pinned to suite 1, building it first |
| `make keystone-oracle` · `generator-oracle` · `core-go-oracle` | the **reference oracle** on the same peers through the same drivers — the other instrument |
| `make differential` | joins every collected run **by requirement id** into `output/DIFFERENTIAL.md` |

`make differential` also lists every check the reference oracle executed for which this repo has
**no requirement at all**. That list is the next authoring batch's worklist: **agreement is not
coverage.**

### The peer under test

| Target | What it does |
|---|---|
| `make peers` | expands the declared peer set from `suites/*/PEERS.diag` — membership is a **rule** (a roster minus declared exclusions), not a hand-typed list |
| `make peer-identity PEER=<name>` | that peer's identity and pin, and whether it is certified by a run contract or merely pinned. **A pin says which bytes; a certification says they were checked** |
| `make peer-up` | starts the reference implementation's peer locally. `SEED_POLICY=<file>` declares the posture; empty means the specification's own bootstrap default |
| `make peer-down` | stops and removes it |
| `make substrate-go` | builds the reference image using that project's own build, never a recipe of ours |
| `make oracle-run` | the reference oracle against the local peer, writing its report and its declared posture to `output/` |
| `make register` | the reference check register, as JSON |

⭐ **A cross-peer check must not fix the language of the other side.** The peer pair is a
**parameter**. Where the full matrix is too expensive to run, the pairs actually run are declared —
a cross-peer result that does not say which two peers produced it is not a result.

## 3. The corpus and its identity

| Target | What it does |
|---|---|
| `make corpus` | the canonical-CBOR build of `requirements/` → `output/requirement-corpus.cbor` and its one content digest |

Three digests exist and they are **not interchangeable**: what corpus exists · what a given build
can run · **what a published number means**. A verdict is anchored on the third — a digest over the
assertions the run actually made, computed by the instrument's own codec.

## 4. The gates

Each runs alone and each carries `--self-test`, which asserts the gate still refuses a planted
defect. A gate with no demonstrated negative control has not been shown to measure anything.

```
make lint-requirements   lint-items        lint-sources       lint-spec-data
make lint-suite-independence   lint-suite-slot   lint-suite-constants
make lint-peer-diversity lint-implements   lint-control-set
make lint-ignored        lint-inbox        lint-codec-agreement
```

Two are worth naming to anyone building a suite:

- **`lint-suite-independence`** — no suite may be written in the reference oracle's language, and no
  suite may take a dependency the cohort already shares. A shared language is shared idioms; a
  shared library is a shared bug. Cryptography and codecs are written from the RFCs.
- **`lint-codec-agreement`** — this tree contains two independent canonical-CBOR encoders, and they
  are compared on every run. They disagreed on the corpus's own map-key ordering rule for this
  repo's entire life and nothing compared them. **Before adding a third implementation of anything,
  add the comparison first.**

## 5. The suite interface

Any suite is an executable at `output/bin/<name>`. This is the contract a consumer swaps across;
`docs/DESIGN-THE-SUITE-CONTRACT.md` is normative for it, and the flag names are inherited from the
reference oracle deliberately — renaming them to win a coupling argument would invalidate every
published number in the ecosystem, and the coupling that matters is expected values, not spelling.

| Flag | Meaning |
|---|---|
| `--addr <host:port>` | the peer under test |
| `--profile <core\|full>` | which requirement set |
| `--requirements <id,…>` / `--category <name>` | scope the run |
| `--peer <label>=<addr>` *(repeatable)* | counterparties for cross-peer requirements |
| `--json-out <path>` | the verdict document |
| `--posture <file>` / `--posture-grants …` | **the declared preconditions the run assumed** |
| `--allow-skip <id,…>` | intentional skips, declared |
| `--list-requirements` | what this suite implements, machine-readable, without running anything |

`--list-requirements` is the one with no precedent, and it is what makes joint coverage computable:
*"suite A reaches 28, suite B reaches 3, together 28"* is a query, not an estimate. Each row carries
the requirement id, the snapshot, and **the sha256 of the obligation text the check was written
against**.

### Verdicts

`PASS` (the conformant arm held **and** the negative control discriminated) · `WARN` (a SHOULD-level
obligation not met) · `FAIL` · `INCONCLUSIVE` (the control did not discriminate — never a pass) ·
`SKIP` (a precondition was unmet, or the peer did something the requirement's arms do not classify,
which is a finding about **the requirement**).

⛔ **Every verdict records the posture it ran in.** A check declares the preconditions it assumes —
granted scopes, seeded identities, installed handlers — **as data**. A precondition stated only as
English inside a skip message is not declared. Running one instrument against one peer under two
different postures changed the size of the check set and moved dozens of severities, all in one
direction, and nothing in either report said which posture was which, because the verdict document
had no field for it. That is why this field exists and why it is not optional.

### Reproducing a published number

A number is quoted as `N·0F @ <digest>` with its pass/warn/fail/skip breakdown, never as a bare
percentage, and **a skip counts as a failure.** The digest anchors the exact assertions the run
made. Given the digest, the snapshot and the declared peer set and posture, a run reproduces or the
difference is a finding.
