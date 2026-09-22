# py-prototype — the hand-written prototype suite

Python 3.12, **stdlib only**, written from the pinned snapshot `spec-data/entity-core-protocol/v0.8.2.21` and the requirement files
listed in `IMPLEMENTS`. It shares no code with any peer, oracle, or other suite, and **no language with the reference
oracle** (`AP-10`; `make lint-suite-independence`).

| File | What | Written from |
|---|---|---|
| `prototype/cbor.py` | canonical encoder; decoder that REPORTS non-ECF input instead of hiding it | RFC 8949, `ENTITY-CBOR-ENCODING` §3–§6 |
| `prototype/ed25519.py` | Ed25519, pure Python | RFC 8032 §5.1 — not a library, so not the library the Go cohort shares |
| `prototype/ident.py` | content hash, peer id, Base58, signatures | core §1.2, §1.5, §3.5, §7.1–§7.4 |
| `prototype/wire.py` | §1.6 framing, envelopes, the §4 handshake; every read returns an *outcome*, never an exception | core §1.6, §3, §4 |
| `prototype/emitted.py` | predicates over what a peer emits (hash recomputation and shape, `included` keys, canonical frames, §3 field types, null optionals); each control re-runs one over fixtures that must fail | core §1.2, §1.3, §2.5, §3.1, §3.5, §3.6; ENCODING §4.1 |
| `prototype/checks.py` | one function per requirement; arms named as in the TOML | the requirement files |
| `run.py` | slot-compatible argv, the verdict document | `docs/DESIGN-THE-SUITE-CONTRACT.md` §1–§2 |
| `launcher.sh` | the one file a slot execs | — |

## Why a bundled interpreter

Keystone's census `--probe` and the generator's `host-launch` exec the instrument **inside each peer's own toolchain
image**, and no interpreter is common to those images. `make build` assembles `output/bin/py-prototype` + `output/bin/py-prototype.d/`:
a pinned python-build-standalone CPython (musl, sha256-checked) and the musl loader from a digest-pinned alpine, started
through the loader so the image's libc is never consulted. Measured on Keystone python/rust/node24/go, core-go and
alpine images, all `--network=none`. Nothing is installed on the host.

## Verdicts

PASS (conformant arm held **and** the negative control discriminated) · WARN (a SHOULD-level requirement not met) · FAIL ·
INCONCLUSIVE (the control did not discriminate: never a pass) · SKIP (precondition unmet, could not look, or an outcome the
requirement's arms do not classify, which is a finding about the *requirement*). **A verdict reached while any connection to the
peer failed to open is withheld as SKIP** (`F57`): a connection that never opened is not the peer refusing anything, and
`tests/test_manifest.py` `NoPeer` holds every check to that. Each result carries witnesses, including **the grant the
handshake actually issued**: the posture as observed on the wire, not as read from a launch script.

Top-level `peer/status/code/trusted` and `summary.*` exist because Keystone's census reads them (`F41`). `trusted` means
the instrument was sound for the run (self-check passed, no suite defect, no INCONCLUSIVE); it says nothing about
whether the peer passed.

```
make build test                 # bundle; codec vs the 71-vector ECF corpus, Ed25519 vs RFC 8032 §7.1
make keystone-s1                # KEYSTONE_PEERS=...           (census --probe slot)
make generator-s1               # GENERATOR_TARGETS=...        (host-launch CLIENT= slot)
make peer-up core-go-s1         # core-go, bootstrap posture
make differential               # every instrument, by requirement id → output/DIFFERENTIAL.md
```

**Surfaces a posture decides.** `system/tree:put` (the `encoding` put rows) and the policy subtree plus
`system/capability:configure` (`peer_canonicalization`) are reachable only under a grant that covers them. A `403` there is
**never scored**: the member is UNMEASURABLE under that posture, and the handshake grant is in the witnesses. core-go's
bootstrap grant covers neither, so it runs once per declared posture, each filed as its own peer row:

```
make peer-up SEED_POLICY=postures/tree-put-on-probe-root.seed-policy.json
make core-go-s1 core-go-oracle CORE_GO_LABEL=entity-peer-tree-put
```

Diagnostic flags: `-requirements ECP-R1,ECP-R6` · `-sign-message hash33|digest32|ecf` (F30) · `-posture-grants <label>`
· `-posture-pre-dispatch-layer` · `-declared-max-payload <bytes>` (the peer's §4.10(a) bound, from its posture; absent, `ECP-R66`
SKIPs) · `-list-requirements`.

**Python hazards this suite had to refuse, recorded so the next suite in the next language looks for its own:** `True`
is an `int` (a `status: true` is not status 1: `wire.classify`); `1`, `1.0` and `True` collapse to one dict key where
CBOR has three (`cbor._Reader.map` refuses the input rather than merge it); `-0.0 == 0.0` and `nan != nan` (the corpus
test compares with sign and NaN kept).

Adding a requirement: implement `check_rN` in `prototype/checks.py`, add it to `CHECKS` and `IMPLEMENTS`, lower
`requirements/UNEXECUTED-CEILING`, then run the loop (`AGENTS.md`).
