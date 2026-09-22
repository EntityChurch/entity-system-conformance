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

.PHONY: help build test lint lint-native lint-spec-data lint-requirements check clean \
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
PEER_ARGS    ?=
PROFILE      ?= core
CATEGORY     ?=
OUT          ?= output

help:
	@echo "entity-system-conformance — host needs make + podman + python3 (>=3.11, stdlib only)."
	@echo
	@echo "  lint        spec-data digests + ECP id index + requirement schema, in $(PYTHON_IMAGE)"
	@echo "  lint-native the same on host python3 (in the host contract; unpinned interpreter version)"
	@echo "  check       build + test + lint"
	@echo "  build/test  no suites under suites/ yet"
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

build:
	@echo "build: no suites under suites/ yet — AGENTS.md, bring-up step 6."

test:
	@echo "test: no suites under suites/ yet."

lint: lint-spec-data lint-requirements

# The snapshot contract, enforced rather than promised. Each gate carries its own executed control.
lint-spec-data:
	@$(PY) tools/spec-snapshot-gate.py --self-test
	@$(PY) tools/spec-snapshot-gate.py

# The requirement format, and the ECP id index it binds against (ids are POSITIONAL).
lint-requirements:
	@$(PY) tools/ecp-index.py --self-test
	@$(PY) tools/ecp-index.py --check
	@$(PY) tools/requirement-gate.py --self-test
	@$(PY) tools/requirement-gate.py

lint-native:
	@echo "lint-native: host python3 — sanctioned, but the interpreter version is not pinned; reports cite make lint." >&2
	@$(MAKE) --no-print-directory lint PY=python3

check: build test lint

clean:
	rm -rf $(OUT)/ scratch/

# ── substrate ─────────────────────────────────────────────────────────────────────────────────
substrate-go:
	$(MAKE) -C $(SUBSTRATE_GO) build

peer-up:
	@podman network exists $(NET) || podman network create $(NET) >/dev/null
	@podman rm -f $(PEER_NAME) >/dev/null 2>&1 || true
	podman run -d --name $(PEER_NAME) --network $(NET) $(PODMAN_CAPS) \
		$(if $(SEED_POLICY),-v $(abspath $(SEED_POLICY)):/posture/seed-policy.json:ro$(comma)Z) \
		$(GO_IMAGE) entity-peer -addr 0.0.0.0:$(PEER_PORT) \
		$(if $(SEED_POLICY),--seed-policy-file /posture/seed-policy.json) $(PEER_ARGS)
	@for i in $$(seq 1 40); do podman logs $(PEER_NAME) 2>&1 | grep -q "Ready to accept" && break; sleep 0.25; done
	@podman logs $(PEER_NAME) 2>&1 | grep -E "Peer ID|Listening|Ready"

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
