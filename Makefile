# entity-system-conformance — make is the build interface (AGENTS-STANDARD).
#
# The host contract is make + podman + python3 (>= 3.11, STDLIB ONLY). Every target runs in a
# container by default; `-native` variants are an explicit opt-in.
#
# 2026-09-12: `lint` previously ran `python3 tools/*.py` on the host, and a handoff told the next
# session to `go build` a peer. The second was the corner this repo exists to refuse — a result that
# only reproduces on a machine with a language toolchain installed is a posture nobody declared.
# The first was ruled acceptable the same day (operator): host python3 is part of the ecosystem's
# host contract, not yet formalized in AGENTS-STANDARD. The boundary kept is the generator seat's
# (`entity-system-generator` ADR-0001): host python is stdlib-only; anything needing a third-party
# library runs in a container. `lint` stays containerised so the interpreter version is pinned.

.PHONY: help build corpus test fmt lint lint-native lint-version lint-version-selftest lint-ignored lint-sources lint-spec-data lint-requirements lint-items check clean \
        install-probe require-suite require-peers peers peer-identity inbox lint-inbox lint-suite-slot lint-codec-agreement \
        keystone-suite generator-suite core-go-suite \
        keystone-s1 keystone-oracle generator-s1 generator-oracle core-go-s1 core-go-oracle differential \
        substrate-go peer-up peer-down oracle-run register
.DEFAULT_GOAL := help

# ── containers ────────────────────────────────────────────────────────────────────────────────
PYTHON_IMAGE ?= docker.io/library/python:3.12-slim
CAP_MEM      ?= 2g
CAP_PIDS     ?= 1024
PODMAN_CAPS  := --memory=$(CAP_MEM) --memory-swap=$(CAP_MEM) --pids-limit=$(CAP_PIDS)

# The repo is bind-mounted read-only: lint reads, never writes.
PY = podman run --rm $(PODMAN_CAPS) -v $(CURDIR):/src:ro,Z -w /src $(PYTHON_IMAGE) python3

# ── substrate: consumed peers and the reference oracle, via THEIR OWN make targets ────────────
# We do not build peers. We ask the owning repo's `make build` for its image and run that image.
SUBSTRATE_GO ?= ../entity-core-go
GO_IMAGE     ?= localhost/entity-core-go
NET          ?= cnf-net
PEER_NAME    ?= cnf-peer
PEER_PORT    ?= 9000
# POSTURE is DECLARED, never inherited. Empty SEED_POLICY = the peer's bootstrap default.
SEED_POLICY  ?=
# The label a core-go run is filed under. A second posture is a second peer row, never an overwrite of the first:
#   make peer-up SEED_POLICY=postures/tree-put-on-probe-root.seed-policy.json
#   make core-go-s1 core-go-oracle CORE_GO_LABEL=entity-peer-tree-put
CORE_GO_LABEL ?= entity-peer
PEER_ARGS    ?=
PROFILE      ?= core
CATEGORY     ?=
OUT          ?= output

help:
	@echo "entity-system-conformance — host needs make + podman + python3 (>=3.11, stdlib only)."
	@echo
	@echo "  lint        spec-data digests + ECP id index + requirement schema + source read-state, in $(PYTHON_IMAGE)"
	@echo "  lint-native the same on host python3 (in the host contract; unpinned interpreter version)"
	@echo "  check       build + test + lint"
	@echo "  build       suite 1 ($(S1)) -> $(S1_BIN) + $(S1_BIN).d (pinned interpreter, requirement digests)"
	@echo "              ⛔ builds ONE suite. Any other suite is DELIVERED as an executable, not built here."
	@echo "  test        suite 1's codec vs the ECF corpus, Ed25519 vs RFC 8032, in the pinned interpreter"
	@echo "  fmt         reformats NOTHING, and prints the whole list of why — there is no formatter here"
	@echo "  clean       remove $(OUT)/ and scratch/"
	@echo
	@echo "  ⭐ the run path takes SUITE=<name> (default $(SUITE)); see require-suite for what a suite must supply"
	@echo "  keystone-suite  SUITE on KEYSTONE_PEERS via keystone census --probe  (default set: $(KEYSTONE_PEERS))"
	@echo "  generator-suite SUITE on GENERATOR_TARGETS via host-launch (CLIENT slot)"
	@echo "  core-go-suite   SUITE against core-go entity-peer (after peer-up)"
	@echo "  keystone-s1 / generator-s1 / core-go-s1   the three above pinned to SUITE=$(S1), building it first"
	@echo "  keystone-oracle / generator-oracle / core-go-oracle   validate-peer on the same peers, same drivers"
	@echo "  require-suite   SUITE=<name>: what that suite still has to supply before it can run"
	@echo "  differential    join all collected runs by requirement id -> $(OUT)/DIFFERENTIAL.md"
	@echo "  corpus      canonical CBOR build of requirements/ -> $(OUT)/requirement-corpus.cbor + its digest"
	@echo
	@echo "  peers           expand the declared peer set (suites/*/PEERS.diag) — membership is a RULE, not a list"
	@echo "  peer-identity   PEER=<name>: that peer's identity/pin, and whether it is contract-certified"
	@echo "  ⭐ inbox         sibling ROUTING-* whose To: names us, and which are on no tracker (AP-17)"
	@echo "  the lint parts, each runnable alone and each with a --self-test:"
	@echo "    lint-requirements lint-items lint-sources lint-spec-data lint-suite-independence"
	@echo "    lint-suite-slot lint-suite-constants lint-peer-diversity lint-implements lint-control-set"
	@echo "    lint-ignored lint-inbox lint-codec-agreement lint-version"
	@echo
	@echo "  substrate-go   build the reference image via $(SUBSTRATE_GO)'s own 'make build'"
	@echo "  peer-up        run $(GO_IMAGE) entity-peer as $(PEER_NAME) on network $(NET)"
	@echo "                 SEED_POLICY=<file> declares the posture; empty = bootstrap default"
	@echo "  oracle-run     validate-peer --profile \$$PROFILE [-category \$$CATEGORY] against $(PEER_NAME);"
	@echo "                 JSON report + declared posture written to $(OUT)/"
	@echo "  peer-down      stop and remove $(PEER_NAME)"
	@echo "  register       the reference check register (conformance-register -json) to $(OUT)/register.json"
	@echo
	@echo "See AGENTS.md for what this repo is for and the three prohibitions."

# ── the prototype suite (suites/py-prototype) ────────────────────────────────────────────────────────────────────
# Python, stdlib only, NOT Go (operator, 2026-09-13): the reference oracle and the reference peer are both Go, so
# an instrument in Go would share the one language whose idioms the ecosystem's measurements already carry.
#
# The standard slots exec the instrument inside each peer's own toolchain image, where no interpreter is common.
# So the bundle carries one: a PINNED python-build-standalone CPython (musl) and the musl loader from a PINNED
# alpine, started by suites/py-prototype/launcher.sh. Nothing is installed on the host; both pins are checked by sha256.
# The requirement files the suite implements are digested into the bundle's BUILD.json, so every verdict names
# the exact requirement text it measured. The bundle ALSO carries their canonical CBOR (requirements.cbor), so the
# instrument computes a PER-RUN anchor over what it actually asserted, with its own codec -- GUIDE-CONFORMANCE
# §3.6 item 7 (was §3.1 item 7 until arch renumbered it on 2026-09-16, closing F74's duplicate-number
# defect), which is the clause a published number is accountable to (not §5.1, which is a fixture-corpus
# naming rule; routed to us by entity-system-generator 2026-09-15). That artifact is also where the two
# independent canonical-CBOR codecs meet on the RUN path rather than only in `make test`.
PYRT_URL     ?= https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.12.14%2B20260901-x86_64-unknown-linux-musl-install_only_stripped.tar.gz
PYRT_SHA256  ?= 1f37044c8cdbd74d5ee112a753c65ef209fedd169c98f3e4e748a93e27eb27a4
MUSL_IMAGE   ?= docker.io/library/alpine@sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e
# The requirement corpus this suite is built from. One place, so a layout move is one edit.
REQ_DIR      := requirements/entity-core-protocol
# ⛔ THE BUILD KNOWS ONE SUITE; THE RUN PATH KNOWS NONE. These `S1_*` names are suite 1's and are
# deliberately NOT the generic ones: this Makefile can build exactly one instrument (a bundled
# CPython), and pretending otherwise would be a second name standing in for content. A suite in
# another language is DELIVERED as a binary — it is not built here, and `require-suite` says so
# rather than failing with "no rule to make target".
S1           := py-prototype
S1_BIN       := $(OUT)/bin/$(S1)
S1_REQS      := $(shell awk '!/^#/ && NF {print $$1}' suites/$(S1)/IMPLEMENTS)
S1_SRC       := $(shell find suites/$(S1)/run.py suites/$(S1)/prototype -name '*.py') suites/$(S1)/launcher.sh suites/$(S1)/IMPLEMENTS
CACHE        := $(OUT)/cache
# The pinned interpreter, run on the repo read-only: `make test` executes the same bits the slots will.
PYRT = podman run --rm --network=none $(PODMAN_CAPS) -v $(CURDIR):/repo:ro,Z -v $(abspath $(S1_BIN)).d:/b:ro,Z -w /repo/suites/$(S1) \
	-e PYTHONHOME=/b/pyrt/python -e PYTHONDONTWRITEBYTECODE=1 $(MUSL_IMAGE) /b/pyrt/ld-musl-x86_64.so.1 --library-path /b/pyrt/python/lib /b/pyrt/python/bin/python3.12 -s -B

$(CACHE)/pyrt.tgz:
	@mkdir -p $(CACHE)
	podman run --rm $(PODMAN_CAPS) -v $(abspath $(CACHE)):/cache:Z $(MUSL_IMAGE) \
		sh -c 'wget -q -O /cache/pyrt.tgz.part "$(PYRT_URL)" && cp -L /lib/ld-musl-x86_64.so.1 /cache/ld-musl-x86_64.so.1'
	@echo "$(PYRT_SHA256)  $(CACHE)/pyrt.tgz.part" | sha256sum -c --quiet || { echo "build: interpreter tarball does NOT match PYRT_SHA256 — refusing" >&2; rm -f $(CACHE)/pyrt.tgz.part; exit 2; }
	mv $(CACHE)/pyrt.tgz.part $@

build: $(S1_BIN) $(OUT)/requirement-corpus.cbor

$(S1_BIN): $(S1_SRC) $(CACHE)/pyrt.tgz $(addprefix $(REQ_DIR)/,$(addsuffix .diag,$(S1_REQS)))
	@rm -rf $(S1_BIN).d && mkdir -p $(S1_BIN).d/pyrt $(S1_BIN).d/suite
	tar -xzf $(CACHE)/pyrt.tgz -C $(S1_BIN).d/pyrt
	install -m 0755 $(CACHE)/ld-musl-x86_64.so.1 $(S1_BIN).d/pyrt/ld-musl-x86_64.so.1
	cp -r suites/$(S1)/run.py suites/$(S1)/prototype $(S1_BIN).d/suite/
	@python3 -B tools/build-info.py --req-dir $(REQ_DIR) --loader $(CACHE)/ld-musl-x86_64.so.1 \
		--pyrt-sha256 $(PYRT_SHA256) --musl-image $(MUSL_IMAGE) \
		--out $(S1_BIN).d/suite/BUILD.json \
		--requirements-out $(S1_BIN).d/suite/requirements.cbor $(S1_REQS)
	install -m 0755 suites/$(S1)/launcher.sh $@
	@$@ -list-requirements >/dev/null && echo "build: $@ runs"

# The canonical build of the whole requirement corpus, and its ONE content digest. This is what
# `DESIGN-THE-SUITE-CONTRACT` §2 calls the comparability anchor; before the 2026-09-15 format move
# we sha256'd each file separately, which is a manifest and not an identity.
corpus: $(OUT)/requirement-corpus.cbor
# Host python3 (stdlib only, in the host contract) rather than $(PY): this target WRITES, and the
# lint container mounts the repo read-only on purpose. The digest is content-derived, so the
# interpreter cannot move it -- `make lint` re-derives and prints the same value in the pinned one.
$(OUT)/requirement-corpus.cbor: $(wildcard $(REQ_DIR)/*.diag)
	@mkdir -p $(OUT)
	@python3 -B tools/requirement-corpus.py --out $@

# The codec against the snapshot's ECF corpus and Ed25519 against RFC 8032, before it touches any peer.
# Suite 1's own unit tests, in suite 1's bundled interpreter. A delivered suite brings its own.
test: $(S1_BIN)
	$(PYRT) -m unittest discover -s tests -v

# >>> RUN PATH — suite-generic below this line (lint-suite-slot enforces it) ────────────────────
#
# ⭐ SUITE= IS THE SLOT A SECOND INSTRUMENT LANDS IN, and until 2026-09-16 there was not one: every
# target below named `py-prototype` literally, at 25 sites. `tools/collect-run.py` and
# `tools/peer-binding.py` both already took `--instrument` / `--suite`, so the TOOLS were ready and
# the make layer was the thing that fixed the value. That is the same defect this seat keeps finding
# one level down — an input that decides the outcome, chosen once, by one party, never written down
# — pointed at our own runner. It would have been discovered the day suite 2 delivered a binary and
# there was nowhere to put it.
#
# A suite that is not suite 1 is NOT BUILT HERE. Its author delivers an executable; drop it at
# $(OUT)/bin/<name> (plus an optional <name>.d bundle directory, which suite 1 needs for its
# interpreter and a static binary does not) and declare suites/<name>/PEERS.diag + IMPLEMENTS.
# `make require-suite SUITE=<name>` tells you exactly what is missing.
SUITE        ?= $(S1)
SUITE_BIN    := $(OUT)/bin/$(SUITE)
SUITE_DIR    := suites/$(SUITE)

# ── run it ────────────────────────────────────────────────────────────────────────────────────
# Keystone first: its census driver launches each peer in that peer's own container, exactly as for
# the reference oracle, and swaps in our instrument via its documented probe slot. The launcher and its
# bundle are installed into keystone's GITIGNORED output/s4-oracles/ — their extension point, no tracked
# file touched.
KEYSTONE       ?= ../entity-core-keystone
# ⛔ THE PEER SET IS DECLARED DATA, NOT A VARIABLE (ADR-0003 §7.3 clause 1, built 2026-09-16).
# This line read `KEYSTONE_PEERS ?= python rust go typescript` until then, and the 33- and 37-peer
# runs overrode it on the command line — so the input that decided every number we have published
# was an argument someone happened to type, and no artifact recorded which one. That is AGENTS.md's
# fairness rule (*the peer pair is a parameter*) on the suite/peer axis.
#
# The set now expands from $(SUITE_DIR)/PEERS.diag against keystone's LIVE roster every run:
# membership is a rule (roster minus declared exclusions), never a frozen list that goes stale as
# the cohort grows — which is the defect keystone built tools/peer-tiers.tsv to fix one level down.
# An override is still possible for a scoped diagnostic run; it is visible on the command line and
# the verdict records the identities either way.
# Host python3 (in the contract, operator 2026-09-12) — it must read KEYSTONE's tree, which is
# outside every container mount here. Same precedent as collect-run.py. `?=` is recursive, so this
# expands on use, not on every `make help`.
KEYSTONE_PEERS ?= $(shell python3 -B tools/peer-binding.py --resolve --suite $(SUITE) --source keystone --keystone $(KEYSTONE))
PROBE_NAME     := cnf-$(SUITE)

# The declared peer set, expanded and inspectable — plus one peer's full identity record.
# ⛔ `peer: "zig"` is not a measurement; `peer: zig @ <commit>, host sha256 <…>, contract absent` is.
peers:
	@echo "declared set ($(SUITE_DIR)/PEERS.diag x keystone's live roster):"
	@echo "  keystone ($(words $(KEYSTONE_PEERS))): $(KEYSTONE_PEERS)"
	@echo "  generator: $(GENERATOR_TARGETS) @ $(GENERATOR_COMP)   core-go: $(CORE_GO_LABEL)"
	@python3 -B tools/peer-binding.py --resolve --suite $(SUITE) --keystone $(KEYSTONE) >/dev/null

peer-identity:
	@test -n "$(PEER)" || { echo "usage: make peer-identity PEER=<name>" >&2; exit 2; }
	@python3 -B tools/peer-binding.py --identity $(PEER) --keystone $(KEYSTONE)

# ⭐ AP-17'S ENFORCEMENT POINT — THE INSTRUMENT THAT PULLS. Delivery in this polyrepo is a
# counterpart committing a document to their own tree; there is no notification and no queue, and
# until 2026-09-16 nothing on this side enumerated. Host python3, like --resolve/--identity: it must
# read SIBLING trees, which are outside every container mount here. Read-only, always.
#
# ⛔ DELIBERATELY NOT IN `make check`, and the reason is the rule it serves. check must be runnable
# with no sibling repo present; an inbox gate that cannot see the siblings would report an empty
# inbox, and an empty inbox and an unread one print the same thing. So the live pull is this target,
# run by a person, and `lint-inbox` gates only the PARSER — which is the half a container can see.
#
# ⛔ THE ROOTS ARE A LIST, AND ONE OF THEM WAS MISSING FOR THIS TARGET'S WHOLE LIFE. A single root
# bounds the counterpart set to one parent directory: a counterpart whose tree sits two levels up is
# unreachable by construction, so a packet it addressed to us could not appear in this count no
# matter how carefully it was written. AP-1's bounded negative, pointed at the counterpart list.
# Both roots are passed; a root that does not resolve is reported and exits 2, never skipped.
SIBLING_ROOTS ?= $(dir $(abspath $(KEYSTONE))) $(abspath $(dir $(abspath $(KEYSTONE)))/../..)
inbox:
	@python3 -B tools/inbox.py --self-test
	@python3 -B tools/inbox.py $(addprefix --siblings ,$(SIBLING_ROOTS))

# ⛔ THE FLOOR ON THE SUITE SIDE, the twin of require-peers. A missing instrument must say WHICH
# artifact is absent and how it gets there, because the failure it replaces — make's "no rule to
# make target output/bin/<name>" — reads as a broken Makefile rather than as an undelivered suite.
require-suite:
	@test -x "$(SUITE_BIN)" || { \
	  echo "REFUSING — no instrument at $(SUITE_BIN) for SUITE=$(SUITE)." >&2; \
	  echo "  suite 1 ($(S1)) is built by 'make build'. Any other suite is DELIVERED, not built here:" >&2; \
	  echo "  install its executable at $(SUITE_BIN) (+ $(SUITE_BIN).d if it needs a bundle dir)." >&2; exit 2; }
	@test -f "$(SUITE_DIR)/PEERS.diag" || { \
	  echo "REFUSING — $(SUITE_DIR)/PEERS.diag is missing; the peer set is DECLARED DATA (ADR-0003 §7)." >&2; \
	  echo "  A run whose peer set nobody declared is the input-nobody-wrote-down defect, again." >&2; exit 2; }
	@test -f "$(SUITE_DIR)/IMPLEMENTS" || { \
	  echo "REFUSING — $(SUITE_DIR)/IMPLEMENTS is missing; a verdict must name the requirement ids it claims." >&2; exit 2; }
	@echo "require-suite: SUITE=$(SUITE) — instrument, declared peer set and IMPLEMENTS all present"

install-probe: require-suite
	@rm -rf $(KEYSTONE)/output/s4-oracles/$(PROBE_NAME) $(KEYSTONE)/output/s4-oracles/$(PROBE_NAME).d
	@if [ -d "$(SUITE_BIN).d" ]; then cp -a $(SUITE_BIN).d $(KEYSTONE)/output/s4-oracles/$(PROBE_NAME).d; \
	 else echo "install-probe: $(SUITE) ships no bundle directory (a self-contained binary) — installing the executable alone"; fi
	install -m 0755 $(SUITE_BIN) $(KEYSTONE)/output/s4-oracles/$(PROBE_NAME)

# ⛔ THE FLOOR, because $(shell) SWALLOWS EXIT CODES. If keystone's tree is missing or its roster
# stops parsing, --resolve writes its reason to stderr and nothing to stdout, so KEYSTONE_PEERS
# expands to the empty string and a census over NO PEERS runs clean. An empty cohort validates
# perfectly and reports as a successful run — the same fail-open shape as a glob that has stopped
# matching (item-gate's MIN_ITEMS) and as F57's all-unreachable report. Refuse instead.
require-peers:
	@test -n "$(strip $(KEYSTONE_PEERS))" || { \
	  echo "REFUSING — the declared keystone peer set expanded to EMPTY. $(SUITE_DIR)/PEERS.diag" >&2; \
	  echo "  resolves against $(KEYSTONE)'s roster; run 'make peers' to see why it could not look." >&2; \
	  echo "  A run over zero peers is not a smaller run, it is not a run." >&2; exit 2; }

keystone-suite: require-peers install-probe
	cd $(KEYSTONE) && tools/run-cohort-census.sh --probe $(PROBE_NAME) $(KEYSTONE_PEERS)
	python3 -B tools/collect-run.py keystone --instrument $(SUITE) --src $(KEYSTONE)/output/scratch/$(PROBE_NAME) \
		--keystone $(KEYSTONE) --out $(OUT)/runs $(KEYSTONE_PEERS)

# Suite 1's spelling of the three targets above, kept because AGENTS.md and the workflow document
# name them. They pin SUITE and build first; `-s1` would otherwise become a name that runs whatever
# SUITE happened to be set to, which is the defect this whole section exists to remove.
keystone-s1: $(S1_BIN)
	@$(MAKE) --no-print-directory keystone-suite SUITE=$(S1)

# The reference oracle on the SAME peers, via the same driver, for the differential.
# ⚠ A NON-probe census ends by STAMPING keystone's TRACKED tools/peer-tiers.tsv with the oracle pin.
# Measured 2026-09-13: a no-op only because the stamped ref already matched. Our diagnostic run must
# never move their roster, so: refuse to start if that file is already modified (we could not tell our
# change from theirs), and restore it afterwards if — and only if — this run is what changed it.
keystone-oracle: require-peers
	@git -C $(KEYSTONE) diff --quiet -- tools/peer-tiers.tsv || { echo "keystone-oracle: REFUSING — $(KEYSTONE)/tools/peer-tiers.tsv has uncommitted changes; the census would stamp over them" >&2; exit 2; }
	-cd $(KEYSTONE) && tools/run-cohort-census.sh $(KEYSTONE_PEERS)
	@git -C $(KEYSTONE) diff --quiet -- tools/peer-tiers.tsv || { git -C $(KEYSTONE) checkout -- tools/peer-tiers.tsv; echo "keystone-oracle: the census stamped keystone's roster; restored (it was clean before this run)"; }
	python3 -B tools/collect-run.py keystone --instrument validate-peer --src $(KEYSTONE)/output/scratch/census \
		--keystone $(KEYSTONE) --out $(OUT)/runs $(KEYSTONE_PEERS)

# The generator's composed peers, through ITS one-copy launcher (tools/host-launch). Suite 1 goes through the
# CLIENT= slot, not ORACLE=: same boot protocol, but ORACLE= also starts core-go's entity-peer as a reference
# (for the oracle's `origination` checks), and a non-Go suite with no cross-peer requirement has no business
# needing a Go binary to exist. Mounted the generator's way: the parent tree READ-ONLY with `label=disable`,
# the only writable mount our own output/.
GENERATOR          ?= ../entity-system-generator
GENERATOR_TARGETS  ?= python rust typescript
GENERATOR_COMP     ?= content
GEN_RUN = podman run --rm --network=none --security-opt label=disable --timeout 900 \
	-v $(abspath $(KEYSTONE)/..):/church:ro -w /church/$(notdir $(abspath $(GENERATOR))) \
	-v $(abspath $(OUT))/runs/generator:/out
gen_image = $$(python3 -c "import tomllib;print(tomllib.load(open('$(GENERATOR)/languages/'+'$$t'+'/profile.toml','rb'))['toolchain']['image'])")

generator-suite: install-probe
	@mkdir -p $(OUT)/runs/generator/$(SUITE)
	@for t in $(GENERATOR_TARGETS); do \
		echo "== generator $$t/$(GENERATOR_COMP): $(SUITE) (CLIENT slot)"; \
		$(GEN_RUN) -e CLIENT=/church/$(notdir $(abspath $(KEYSTONE)))/output/s4-oracles/$(PROBE_NAME) $(gen_image) \
			./tools/host-launch $$t $(GENERATOR_COMP) -peer $$t-$(GENERATOR_COMP) -profile core -json-out /out/$(SUITE)/$$t-$(GENERATOR_COMP).json \
			| grep -E "^(PASS|FAIL|SKIP|INCON|ERROR|$(SUITE)|    )" ; \
	done
	python3 -B tools/collect-run.py generator --instrument $(SUITE) --src $(OUT)/runs/generator/$(SUITE) --generator $(GENERATOR) \
		--comp $(GENERATOR_COMP) --out $(OUT)/runs $(addsuffix -$(GENERATOR_COMP),$(GENERATOR_TARGETS))

generator-s1: $(S1_BIN)
	@$(MAKE) --no-print-directory generator-suite SUITE=$(S1)

generator-oracle:
	@mkdir -p $(OUT)/runs/generator/validate-peer
	@for t in $(GENERATOR_TARGETS); do \
		echo "== generator $$t/$(GENERATOR_COMP): validate-peer -profile core (every category: a requirement may name a check outside connectivity)"; \
		$(GEN_RUN) $(gen_image) \
			./tools/host-launch $$t $(GENERATOR_COMP) -profile core -json-out /out/validate-peer/$$t-$(GENERATOR_COMP).json | tail -2 ; \
	done
	python3 -B tools/collect-run.py generator --instrument validate-peer --src $(OUT)/runs/generator/validate-peer --generator $(GENERATOR) \
		--comp $(GENERATOR_COMP) --out $(OUT)/runs $(addsuffix -$(GENERATOR_COMP),$(GENERATOR_TARGETS))

# core-go's reference peer on the bootstrap posture (peer-up), our suite in its own container on the network.
# The container is the musl base for suite 1's loader; a static binary runs in it unchanged, which is
# why the brief suggests one — the invocation below is the standard slot, identical for either.
core-go-suite: require-suite
	@test -f $(PEER_POSTURE) || { echo "core-go-suite: COULD NOT LOOK — no $(PEER_POSTURE); run make peer-up (it records the posture)" >&2; exit 2; }
	@mkdir -p $(OUT)/runs/core-go/$(SUITE)
	-podman run --rm --network $(NET) $(PODMAN_CAPS) -v $(abspath $(OUT)):/out:Z $(MUSL_IMAGE) \
		/out/bin/$(SUITE) -addr $(PEER_NAME):$(PEER_PORT) -peer core-go -posture-grants "$$(sed -n 's/^grants=//p' $(PEER_POSTURE))" \
		-json-out /out/runs/core-go/$(SUITE)/$(CORE_GO_LABEL).json
	python3 -B tools/collect-run.py core-go --instrument $(SUITE) --src $(OUT)/runs/core-go/$(SUITE) --posture-file $(PEER_POSTURE) --out $(OUT)/runs $(CORE_GO_LABEL)

core-go-s1: $(S1_BIN)
	@$(MAKE) --no-print-directory core-go-suite SUITE=$(S1)

core-go-oracle:
	@test -f $(PEER_POSTURE) || { echo "core-go-oracle: COULD NOT LOOK — no $(PEER_POSTURE); run make peer-up (it records the posture)" >&2; exit 2; }
	-$(MAKE) --no-print-directory oracle-run OUT=$(OUT)/runs/core-go/validate-peer
	mv $(OUT)/runs/core-go/validate-peer/validate-peer.report.json $(OUT)/runs/core-go/validate-peer/$(CORE_GO_LABEL).json
	python3 -B tools/collect-run.py core-go --instrument validate-peer --src $(OUT)/runs/core-go/validate-peer --posture-file $(PEER_POSTURE) --out $(OUT)/runs $(CORE_GO_LABEL)

# Join every collected run: requirement id ↔ the oracle check each requirement file names.
differential:
	python3 -B tools/differential.py --runs $(OUT)/runs --requirements $(REQ_DIR) --out $(OUT)/DIFFERENTIAL.md
	@cat $(OUT)/DIFFERENTIAL.md

# <<< RUN PATH — end of the suite-generic region ────────────────────────────────────────────────

lint: lint-version-selftest lint-version lint-ignored lint-suite-independence lint-suite-slot lint-codec-agreement lint-suite-constants lint-sources lint-spec-data lint-requirements lint-items lint-peer-diversity lint-implements lint-control-set lint-inbox

# ⭐ THE ENFORCEMENT POINT FOR "NO UNDECLARED VERSION AXIS". `VERSION` is this repository's release
# number. Anywhere else in the tree that states a version either states the same one, or is named
# in `.version-scope` as versioning on its own axis. Undeclared disagreement is the defect.
#
# ⚠ WHY THAT QUESTION AND NOT "do all the numbers match". They legitimately do not: a suite is an
# independent instrument with its own lifecycle, and `suites/rs-conformance` is declared out of
# scope for exactly that reason. A gate demanding equality would be wrong about this tree, and one
# that took the exclusions and then compared what was left would, right now, compare NOTHING and
# print a pass — which is the shape this repository refuses everywhere else. Asking instead whether
# every axis is *declared* has content in every tree, including this one: add a second crate at a
# different number without saying so and this fires.
#
# ⚠ AND WHAT IT STILL DOES NOT DO, stated rather than left to inference. It does not know whether
# the number is the RIGHT one, whether it has been used before, or whether a change is breaking —
# none of those is answerable from inside the tree. It reads `Cargo.toml`, `pyproject.toml` and
# `package.json` only, so a version-bearing file of some other kind is invisible to it; the scan
# count prints on every run so that bound is visible rather than assumed.
#
# ⛔ FAIL-CLOSED ON ITS OWN INPUTS: an absent `VERSION`, a `VERSION` that does not read as a release
# number, a manifest with a package table but no version in it, and a `.version-scope` that exists
# and cannot be read are each COULD-NOT-LOOK — never a pass. A declaration that cannot be read is
# not an empty one.
#
# ⭐ AND THE OUTCOME IS PRINTED AS A TOKEN, not left to the exit code, because `make` collapses
# every recipe failure to its own exit 2. Inside a recipe, "a finding" and "could not look" are
# indistinguishable to any caller through that boundary — so `status=CLEAN|FINDING|COULD-NOT-LOOK`
# is the observable, and it is what the self-test asserts. Encoding the distinction only in an exit
# code nothing can read would have been a distinction on paper.
#
# ⭐ `VSROOT` IS WHAT MAKES IT TESTABLE — the tree it reads, defaulting to this one. `make
# lint-version-selftest` points it at planted trees and asserts each refusal, which is this
# repository's floor for a gate: a check that cannot be made to fail has not been shown to measure
# anything, and that applies to the checks as hard as it applies to the requirements.
VSROOT ?= .

lint-version:
	@set -e; cd $(VSROOT) 2>/dev/null || { echo "lint-version: status=COULD-NOT-LOOK — $(VSROOT) is not a readable directory" >&2; exit 2; }; \
	 cnl() { echo "lint-version: status=COULD-NOT-LOOK — $$1" >&2; exit 2; }; \
	 test -f VERSION || cnl "VERSION is absent"; \
	 v=$$(head -n1 VERSION | tr -d '[:space:]'); \
	 case "$$v" in [0-9]*.[0-9]*.[0-9]*) ;; \
	   *) cnl "VERSION does not read as a release number: '$$v'";; esac; \
	 pats=''; \
	 if [ -e .version-scope ]; then \
	   [ -r .version-scope ] || cnl ".version-scope exists and cannot be read"; \
	   pats=$$(sed 's/#.*//' .version-scope | tr -s '[:space:]' '\n' | grep . || true); \
	 fi; \
	 files=$$(find . -path ./.git -prune -o -path ./$(OUT) -prune -o -path ./scratch -prune -o \
	          -path './suites/*/target' -prune -o -type f \
	          \( -name Cargo.toml -o -name pyproject.toml -o -name package.json \) -print \
	          | sed 's|^\./||' | sort); \
	 scanned=0; declared=0; bad=0; hit=''; \
	 for f in $$files; do \
	   scanned=$$((scanned+1)); \
	   case "$$f" in \
	     *.json) fv=$$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$$f" | head -n1); tbl=1;; \
	     *) tbl=$$(grep -cE '^[[:space:]]*\[(package|project|tool\.poetry|workspace\.package)\][[:space:]]*$$' "$$f" || true); \
	        fv=$$(awk '/^[[:space:]]*\[/{t=$$0;sub(/^[[:space:]]*\[/,"",t);sub(/\].*$$/,"",t)} \
	                   /^[[:space:]]*version[[:space:]]*=/{ \
	                     if(t=="package"||t=="project"||t=="tool.poetry"||t=="workspace.package"){ \
	                       s=$$0; sub(/^[^"]*"/,"",s); sub(/".*$$/,"",s); print s; exit}}' "$$f");; \
	   esac; \
	   if [ "$$tbl" != "0" ] && [ -z "$$fv" ]; then \
	     echo "lint-version: $$f declares a package table and no version could be read from it" >&2; bad=2; continue; \
	   fi; \
	   [ -n "$$fv" ] || continue; \
	   inscope=0; \
	   for p in $$pats; do \
	     case "$$f" in "$$p"|"$$p"/*) inscope=1; hit="$$hit $$p";; \
	       *) case "$$f" in $$p) inscope=1; hit="$$hit $$p";; esac;; esac; \
	   done; \
	   if [ "$$inscope" = 1 ]; then \
	     declared=$$((declared+1)); \
	     echo "lint-version:   out of scope per .version-scope — $$f ($$fv), its own axis"; \
	   elif [ "$$fv" != "$$v" ]; then \
	     echo "lint-version: $$f is $$fv, VERSION is $$v, and .version-scope does not name it. Either bump it with the release, or declare the axis it is really on" >&2; bad=1; \
	   fi; \
	 done; \
	 for p in $$pats; do \
	   case " $$hit " in *" $$p "*) ;; \
	     *) echo "lint-version: ⚠ .version-scope names '$$p', which matched no file — a declaration that has stopped describing the tree. Reported, not refused.";; esac; \
	 done; \
	 if [ "$$bad" = 2 ]; then echo "lint-version: status=COULD-NOT-LOOK — a manifest above could not be read for a version, so this run did not cover the tree" >&2; exit 2; fi; \
	 if [ "$$bad" = 1 ]; then echo "lint-version: status=FINDING — an undeclared version axis, above" >&2; exit 1; fi; \
	 echo "lint-version: status=CLEAN — $$v, $$scanned manifest(s) scanned, $$declared on a declared separate axis, 0 undeclared disagreement(s)"

# The self-test. Each case plants ONE defect in an otherwise clean tree and asserts the STATUS the
# gate reports, because the three outcomes have to stay distinguishable: CLEAN · FINDING · COULD
# NOT LOOK. The control at the end is the one that matters — the clean tree must still pass, or
# every refusal above is being produced by something other than the defect.
#
# ⚠ It re-enters through `$${MAKE:-make}` rather than `$(MAKE)` on purpose: `make` treats a literal
# `$(MAKE)` as a recursive call and runs the line even under `-n`, so a dry run of `lint` executed
# this whole self-test in dry-run mode and reported a failure that was an artifact of `-n`.
lint-version-selftest:
	@set -e; T=$$(mktemp -d); trap 'chmod -R u+rwX "$$T" 2>/dev/null; rm -rf "$$T"' EXIT; \
	 mk() { d="$$T/$$1"; mkdir -p "$$d/sub"; printf '0.4.0\n' > "$$d/VERSION"; \
	        printf '[package]\nname = "x"\nversion = "0.4.0"\n' > "$$d/sub/Cargo.toml"; }; \
	 want() { set +e; got=$$($${MAKE:-make} -s lint-version VSROOT="$$T/$$1" 2>&1 | sed -n 's/.*status=\([A-Z-]*\).*/\1/p' | tail -n1); set -e; \
	          if [ "$$got" != "$$2" ]; then echo "lint-version-selftest: FAIL — $$1 reported '$$got', wanted '$$2'" >&2; exit 1; fi; \
	          echo "  ok  $$1 -> $$2  ($$3)"; }; \
	 mk absent-version; rm "$$T/absent-version/VERSION"; \
	 mk unreadable-version; printf 'nightly\n' > "$$T/unreadable-version/VERSION"; \
	 mk unreadable-scope; printf 'sub/Cargo.toml\n' > "$$T/unreadable-scope/.version-scope"; \
	   chmod 000 "$$T/unreadable-scope/.version-scope"; \
	 mk no-version-in-table; printf '[package]\nname = "x"\n' > "$$T/no-version-in-table/sub/Cargo.toml"; \
	 mk undeclared-disagreement; printf '[package]\nname = "x"\nversion = "9.9.9"\n' > "$$T/undeclared-disagreement/sub/Cargo.toml"; \
	 mk declared-disagreement; printf '[package]\nname = "x"\nversion = "9.9.9"\n' > "$$T/declared-disagreement/sub/Cargo.toml"; \
	   printf '# its own axis\nsub/Cargo.toml\n' > "$$T/declared-disagreement/.version-scope"; \
	 mk declared-by-prefix; printf '[package]\nname = "x"\nversion = "9.9.9"\n' > "$$T/declared-by-prefix/sub/Cargo.toml"; \
	   printf 'sub\n' > "$$T/declared-by-prefix/.version-scope"; \
	 mk declared-by-glob; printf '[package]\nname = "x"\nversion = "9.9.9"\n' > "$$T/declared-by-glob/sub/Cargo.toml"; \
	   printf '*/Cargo.toml\n' > "$$T/declared-by-glob/.version-scope"; \
	 mk rotted-scope; printf 'long/gone/Cargo.toml\n' > "$$T/rotted-scope/.version-scope"; \
	 mk clean; \
	 want absent-version           COULD-NOT-LOOK "absent input is never a pass"; \
	 want unreadable-version       COULD-NOT-LOOK "a VERSION that is not a release number is could-not-look"; \
	 want unreadable-scope         COULD-NOT-LOOK "a declaration that cannot be read is not an empty one"; \
	 want no-version-in-table      COULD-NOT-LOOK "a package table whose version cannot be read is could-not-look"; \
	 want undeclared-disagreement  FINDING "the defect this gate exists for"; \
	 want declared-disagreement    CLEAN "a declared separate axis is not a disagreement"; \
	 want declared-by-prefix       CLEAN "a directory prefix covers everything under it"; \
	 want declared-by-glob         CLEAN "a glob matches"; \
	 want rotted-scope             CLEAN "an entry matching nothing is reported, never a refusal"; \
	 want clean                    CLEAN "the control — a clean tree still passes"; \
	 echo "lint-version self-test: OK — 10 case(s), 4 refusals and 1 finding each produced by ONE planted defect"

# ⭐ THE ENFORCEMENT POINT FOR SUITE=, without which it is a convention and decays back into a
# constant on the first hurried edit. Between the RUN PATH markers, no recipe may name a suite
# literally — comments may, because naming the incident is the opposite of depending on it (the
# same carve-out docs/SOURCES-CITATION-DEBT had to make on its first day).
#
# ⚠ WHAT THIS DOES NOT DO, stated rather than left to inference: it checks the run path only, it
# only knows the suites that exist in suites/, and it cannot tell a generic recipe from one that is
# generic and wrong. It fires on the regression it was built for, and on nothing else.
#
# ⭐ It caught one on its first run: require-peers' REFUSING message still named
# `suites/py-prototype/PEERS.diag` literally, so a suite-2 run over an empty peer set would have
# told the operator to go read suite 1's declaration. A wrong-but-plausible diagnostic is the worst
# kind — it parses, it is actionable, and it sends you to the wrong file.
# ⚠ Graded BUILT, not SOLID: what it caught was this session's own incomplete edit, not an
# independent regression by someone who had not just written the gate. That is a weaker claim than
# the scale's "has caught a real incident" and it is the honest one.
# ⭐ THE TWO CODECS IN THIS REPO MUST AGREE. tools/cbordiag.py (the requirement corpus) and
# suites/py-prototype/prototype/cbor.py (the instrument, on the wire) are two independent canonical
# CBOR encoders -- and NOTHING COMPARED THEM until 2026-09-17, when they turned out to disagree on
# the corpus's own map-key ordering rule (cbordiag was RFC 8949 §4.2.1 bytewise; the rule is §4.2.3
# length-first, arch's F22/CQ-15 ruling). Latent -- every corpus key is text and the orderings
# provably coincide there -- so requirement_corpus_digest did not move and nothing republished.
#
# ⛔ THE FINDING IS NOT THE BUG, IT IS THAT WE ALREADY HAD THE SECOND IMPLEMENTATION. This seat's
# entire argument is that two independent implementations catch each other; we ran two for the
# repo's whole life with no instrument between them, and the disagreement was found by reading a
# counterpart's packet. ⭐ SOLID: restore the bytewise sort and this gate fires on the real defect.
lint-codec-agreement:
	@$(PY) tools/codec-agreement.py --self-test
	@$(PY) tools/codec-agreement.py

# The half of the inbox a container can see: the addressee parser. The live pull is `make inbox`
# and needs the sibling trees. ⚠ This gate passing says the parser is right, NOT that the inbox is
# empty -- and those two are easy to confuse in a green run, which is why it prints the difference.
lint-inbox:
	@$(PY) tools/inbox.py --self-test
	@echo "lint-inbox: the PARSER is gated; the inbox itself is not. Run 'make inbox' — it needs the sibling trees."

lint-suite-slot:
	@test -n "$$(sed -n '/^# >>> RUN PATH/,/^# <<< RUN PATH/p' Makefile)" || { \
	  echo "lint-suite-slot: COULD NOT LOOK — the RUN PATH markers are gone from the Makefile" >&2; exit 2; }
	@bad=$$(sed -n '/^# >>> RUN PATH/,/^# <<< RUN PATH/p' Makefile | grep -vE '^[[:space:]]*#' \
	        | grep -nE "$$(ls -d suites/*/ | xargs -n1 basename | paste -sd'|')"); \
	 if [ -n "$$bad" ]; then \
	   echo "lint-suite-slot: the run path names a suite literally; it must use \$$(SUITE):" >&2; \
	   echo "$$bad" >&2; exit 1; fi
	@echo "lint-suite-slot: the run path names no suite literally (SUITE=$(SUITE), $$(ls -d suites/*/ | wc -l) suite(s) declared)"

# Stage 7 of docs/WORKFLOW-SUITE-BRINGUP.md — the expected-outcome set, pinned to the obligation it
# was measured against. Operator direction 2026-09-16: a bring-up chunk must not be built against
# requirements whose answers we do not already know, because a suite reporting FAIL everywhere and a
# suite that is simply BROKEN produce identical output. So `fit_for_bringup` requires both a PASS and
# a FAIL on real peers, and that is checked rather than asserted.
#
# ⛔ Rule 1 is the one that earned the file. The first draft recorded `ECP-R3: 3 PASS` from the 06:42
# run — verdicts scored against requirement text that no longer existed, because ECP-R3 was
# re-authored between that run and HEAD (9714ce72… → 08155caf…). Every row now pins the requirement's
# sha256 and the gate recomputes it, so a moved obligation reds instead of silently invalidating the
# expectations under it. Shown to catch that exact incident: restore the morning digest and it fires.
lint-control-set:
	@$(PY) tools/control-set-gate.py --self-test
	@$(PY) tools/control-set-gate.py

# F76. Every other suite-facing gate measures a DECLARATION that the suite implements an id; none
# could see WHICH VERSION of the obligation the code implements. ECP-R57's obligation inverted and
# check_r57 scored the old rule for a day; ECP-R7's code was pinned at .24 and check_r7 accepted any
# refusal for two. `make check` was green through both. This gate compares the snapshot each check
# was AUTHORED against to the one its requirement is authored at, and ratchets the `unreviewed`
# count in suites/IMPLEMENTS-REVIEW-DEBT (26 of 28 at first measurement).
lint-implements:
	@$(PY) tools/implements-gate.py --self-test
	@$(PY) tools/implements-gate.py

# ADR-0003 §7.3 clause 3. ⚠ VACUOUS TODAY AND IT SAYS SO ON EVERY RUN — one suite exists, so
# "two suites' peer sets" has no instance and clause 1 CANNOT fire. That is the point of building it
# now: it fails the moment suite 2 declares an overlapping set, instead of being written afterwards
# by someone who has already chosen. A gate that cannot fail yet is honest only if it reports that.
#
# Runs on CONTAINER python against our own tree only (PEERS.diag), so it needs no sibling repo —
# unlike --resolve/--identity, which consume keystone's roster and run on the host.
lint-peer-diversity:
	@$(PY) tools/peer-binding.py --self-test
	@$(PY) tools/peer-binding.py --lint

# D17 / audit A6 pass C (2026-09-14, landed 2026-09-15). THE GAP THIS CLOSES: every other gate here
# measures content WE PRODUCED, and all of them were green through four sessions in which this seat
# cited a 1,094-line governing document nobody had opened. Nothing measured whether the INPUTS were
# read, and nothing ever would by accident — a gate cannot see an absence unless something makes it
# look. This one fails on a citation into a document docs/SOURCES.md records as unread, and on an
# inventory row with no read state or no date. Its debt ledger is docs/SOURCES-CITATION-DEBT.
lint-sources:
	@$(PY) tools/sources-gate.py --self-test
	@$(PY) tools/sources-gate.py

# AP-10 (candidate): no suite is written in the reference oracle's language, and no suite reaches into another suite
# or into tools/. Shared code is shared bugs; a shared language with the oracle is shared idioms and shared libraries.
#
# ⛔⭐ THE NEGATION CARVE-OUT, added 2026-09-17, AND IT FIRED ON THE FIRST SECOND SUITE THAT EVER
# EXISTED. `suites/rs-conformance/src/main.rs` opens with a module comment declaring WHAT IT DID NOT
# READ -- "⛔ WHAT THIS SUITE DID NOT READ, because that is the whole point of it existing:
# `suites/py-prototype/**` …". The gate greps for the literal path and cannot tell "I read this"
# from "I declare I did not read this", so it refused the honest act, in the one file where that
# declaration is most useful to a reviewer.
#
# THIS IS THE SECOND INSTANCE OF ONE SHAPE HERE. docs/SOURCES-CITATION-DEBT had it on day one: the
# STATUS entry REPORTING the debt cited the unread section three more times and the ratchet refused
# the commit. Its note is the rule: "Describing a gap is the opposite of relying on it, and a gate
# that punishes the honest act is a gate people route around."
#
# ⚠ SCOPE, because the weakening must be bounded: only a line carrying an explicit negation is
# exempt. A suite QUOTING another suite's design in a comment still trips -- that is a real leak,
# and a comment cannot be a dependency but it can be evidence of having read one. Like every
# declaration-based gate here (PEERS.diag exclusions, SOURCES read-state), this is auditable rather
# than tamper-proof, and that is the posture on purpose.
ORACLE_LANG_GLOBS := *.go go.mod go.sum   # kept for `make help`; the gate is tools/suite-independence.py
lint-suite-independence:
	@$(PY) tools/suite-independence.py --self-test
	@$(PY) tools/suite-independence.py

# D16 / AP-13 (F43, F65): a run-defining input that the requirement files already carry MUST be derived,
# never restated as a suite constant. Its planted controls, its hole and why it is now a tool rather than
# a grep are all documented in tools/suite-constants-gate.py's header.
lint-suite-constants:
	@$(PY) tools/suite-constants-gate.py --self-test
	@$(PY) tools/suite-constants-gate.py

# The gates below read the WORKING TREE. A file they validate that .gitignore excludes passes locally and is
# absent from every clone — a green run over something nobody else has. Host git: it is the repository, not a
# language toolchain. Without git this is could-not-look, reported, never a pass.
lint-ignored:
	@command -v git >/dev/null || { echo "lint-ignored: COULD NOT LOOK — no git on host" >&2; exit 2; }
	@ign=$$(git ls-files --others --ignored --exclude-standard -- requirements spec-data tools docs suites \
	        | grep -vE "/(target|__pycache__|node_modules|dist|build)/"); \
	 if [ -n "$$ign" ]; then echo "lint-ignored: gated files excluded by .gitignore:" >&2; echo "$$ign" >&2; exit 1; fi; \
	 echo "lint-ignored: 0 gated files excluded by .gitignore"

# The snapshot contract, enforced rather than promised. Each gate carries its own executed control.
lint-spec-data:
	@$(PY) tools/spec-snapshot-gate.py --self-test
	@$(PY) tools/spec-snapshot-gate.py

# The requirement format, and the ECP id index it binds against (ids are POSITIONAL).
lint-requirements:
	@$(PY) tools/ecp-index.py --self-test
	@$(PY) tools/ecp-index.py --check
	@$(PY) tools/cbordiag.py --self-test
	@$(PY) tools/requirement-corpus.py --self-test
	@$(PY) tools/build-info.py --self-test
	@$(PY) tools/requirement-gate.py --self-test
	@$(PY) tools/requirement-gate.py
	@$(PY) tools/requirement-corpus.py

# ADR-0003's other half. An ITEM is one suite's concrete probe: which bytes to send and which answers
# are conformant. The requirement is shared between suites by design; this is not.
# ⛔ THE MANDATORY NEGATIVE CONTROL LIVES HERE NOW, because the arms it governs moved here. Its
# defects are RE-PLANTED in item-gate.py's self-test rather than assumed to have survived the move.
lint-items:
	@$(PY) tools/item-gate.py --self-test
	@$(PY) tools/item-gate.py

lint-native:
	@echo "lint-native: host python3 — sanctioned, but the interpreter version is not pinned; reports cite make lint." >&2
	@$(MAKE) --no-print-directory lint PY=python3

# ── fmt ───────────────────────────────────────────────────────────────────────────────────────
# Tier-1 verb, and it REFORMATS NOTHING. That is a real answer, not a stub, and it says so out loud
# rather than exiting 0 in silence — a verb that prints nothing and succeeds is indistinguishable
# from one that ran and found nothing to do, which is the fail-open shape this repo refuses.
#
#   suite 1      Python 3.12 STDLIB ONLY, and every target is container-default. Adding a
#                formatter means adding a third-party dependency to the one thing whose whole
#                claim is that it shares no library with anybody.
#   suite 2      DELIVERED, not built here. Its tree is formatted by its author, in their toolchain.
#   requirements canonical CBOR is not a style. `make corpus` re-derives the artifact and its digest
#                MOVES on any content change, so the shape of these files is gated, not formatted.
#                A formatter here would silently re-encode obligations and move digests under
#                verdicts that were scored against them.
#   tools/       stdlib python, checked by `make lint`, which is where a style rule would go.
fmt:
	@echo "fmt: nothing to reformat, deliberately — and this is the whole list:"
	@echo "  suites/py-prototype  stdlib-only by rule; a formatter is a shared dependency (make lint-suite-independence)"
	@echo "  suites/*             any suite that is not suite 1 is DELIVERED; its tree is its author's"
	@echo "  requirements/*.diag  canonical CBOR is GATED, not formatted — re-encoding here moves digests"
	@echo "                       under verdicts already scored against them (make corpus, make lint-requirements)"
	@echo "  tools/               stdlib python; style belongs in 'make lint'"
	@echo "fmt: 0 file(s) changed. If you expected a formatter, the answer is that there is none, not that it found nothing."

check: build test lint

clean:
	rm -rf $(OUT)/ scratch/

# ── substrate ─────────────────────────────────────────────────────────────────────────────────
substrate-go:
	$(MAKE) -C $(SUBSTRATE_GO) build

# The posture is RECORDED BY THE TARGET THAT LAUNCHES THE PEER, and every downstream run reads that record. Until
# 2026-09-13 core-go-s1 passed `-posture-grants bootstrap-default` and collect-run typed the same string, whatever
# SEED_POLICY/PEER_ARGS peer-up had actually been given: a hand-typed posture, in the seat founded on refusing one.
PEER_POSTURE := $(OUT)/peer-up.posture

peer-up:
	@podman network exists $(NET) || podman network create $(NET) >/dev/null
	@podman rm -f $(PEER_NAME) >/dev/null 2>&1 || true
	podman run -d --name $(PEER_NAME) --network $(NET) $(PODMAN_CAPS) \
		$(if $(SEED_POLICY),-v $(abspath $(SEED_POLICY)):/posture/seed-policy.json:ro$(comma)Z) \
		$(GO_IMAGE) entity-peer -addr 0.0.0.0:$(PEER_PORT) \
		$(if $(SEED_POLICY),--seed-policy-file /posture/seed-policy.json) $(PEER_ARGS)
	@mkdir -p $(OUT)
	@printf 'image=%s\nimage_id=%s\nseed_policy=%s\nseed_policy_sha256=%s\npeer_args=%s\ngrants=%s\nstarted_at=%s\n' \
		"$(GO_IMAGE)" "$$(podman image inspect --format '{{.Id}}' $(GO_IMAGE))" \
		"$(if $(SEED_POLICY),$(SEED_POLICY),none)" "$(if $(SEED_POLICY),$$(sha256sum $(SEED_POLICY) | cut -d' ' -f1),-)" "$(PEER_ARGS)" \
		"$(if $(SEED_POLICY),seed-policy:$$(sha256sum $(SEED_POLICY) | cut -c1-16),$(if $(findstring open-access,$(PEER_ARGS)),open-access,bootstrap-default))$(if $(PEER_ARGS), args=$(PEER_ARGS))" \
		"$$(date -u +%s)" > $(PEER_POSTURE)
	@for i in $$(seq 1 40); do podman logs $(PEER_NAME) 2>&1 | grep -q "Ready to accept" && break; sleep 0.25; done
	@podman logs $(PEER_NAME) 2>&1 | grep -E "Peer ID|Listening|Ready"
	@echo "peer-up: posture recorded in $(PEER_POSTURE): $$(grep ^grants= $(PEER_POSTURE))"

oracle-run:
	@mkdir -p $(OUT)
	@printf 'image=%s\nimage_id=%s\npeer_args=%s\nseed_policy=%s\nseed_policy_sha256=%s\nprofile=%s\ncategory=%s\n' \
		"$(GO_IMAGE)" "$$(podman image inspect --format '{{.Id}}' $(GO_IMAGE))" "$(PEER_ARGS)" \
		"$(if $(SEED_POLICY),$(SEED_POLICY),bootstrap-default)" \
		"$(if $(SEED_POLICY),$$(sha256sum $(SEED_POLICY) | cut -d' ' -f1),-)" \
		"$(PROFILE)" "$(if $(CATEGORY),$(CATEGORY),all)" > $(OUT)/posture.txt
	podman run --rm --network $(NET) $(PODMAN_CAPS) --userns=keep-id --user $$(id -u):$$(id -g) \
		-v $(abspath $(OUT)):/out:Z $(GO_IMAGE) \
		validate-peer -addr $(PEER_NAME):$(PEER_PORT) --profile $(PROFILE) \
		$(if $(CATEGORY),-category $(CATEGORY)) -json-out /out/validate-peer.report.json

peer-down:
	-podman rm -f $(PEER_NAME)

# The reference oracle's check register, from the image. The polyrepo parent is mounted READ-ONLY because
# conformance-register reads core-go's validator source and ../entity-system-architecture by relative path.
register:
	@mkdir -p $(OUT)
	podman run --rm $(PODMAN_CAPS) --userns=keep-id --user $$(id -u):$$(id -g) \
		-v $(abspath $(SUBSTRATE_GO)/..):/w:ro,Z -v $(abspath $(OUT)):/out:Z \
		-w /w/$(notdir $(abspath $(SUBSTRATE_GO))) $(GO_IMAGE) sh -c 'conformance-register -json > /out/register.json'

comma := ,
