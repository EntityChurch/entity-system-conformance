# entity-system-conformance — make is the build interface (AGENTS-STANDARD).
#
# Container-default with a -native opt-in, per the ecosystem convention. Nothing is
# built yet: these targets exist, are wired, and are HONEST about being empty rather
# than absent. A missing target reads as "not supported"; an empty one reads as
# "not yet", which is the true state.

.PHONY: build test lint lint-spec-data lint-requirements check clean help
.DEFAULT_GOAL := help

help:
	@echo "entity-system-conformance — bootstrap stage, nothing built yet."
	@echo
	@echo "  build   compile every suite under suites/           (none yet — bring-up step 6)"
	@echo "  test    each suite's own tests                      (none yet — bring-up step 6)"
	@echo "  lint    spec-data digests + ECP id index + requirement schema  (all LIVE)"
	@echo "  check   build + test + lint"
	@echo "  clean   remove run artifacts"
	@echo
	@echo "See AGENTS.md for what this repo is for and the three prohibitions."

build:
	@echo "build: no suites under suites/ yet — AGENTS.md, bring-up step 6."

test:
	@echo "test: no suites under suites/ yet."

lint: lint-spec-data lint-requirements

# The snapshot contract, enforced rather than promised. A snapshot edited in place leaves
# every requirement citing it UNVERIFIED — neither wrong nor right — and announces nothing.
# The gate carries its own executed control; run it with the lint.
lint-spec-data:
	@python3 tools/spec-snapshot-gate.py --self-test
	@python3 tools/spec-snapshot-gate.py

# The requirement format, and the ECP id index it binds against. Both carry executed controls;
# `--check` on the index is what catches a snapshot that moved under the ids (they are POSITIONAL).
lint-requirements:
	@python3 tools/ecp-index.py --self-test
	@python3 tools/ecp-index.py --check
	@python3 tools/requirement-gate.py --self-test
	@python3 tools/requirement-gate.py

check: build test lint

clean:
	rm -rf output/ scratch/
