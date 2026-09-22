#!/bin/sh
# s1-py launcher — the one file an instrument slot execs. The bundle sits beside it at "$0.d".
#
# WHY A SHELL LAUNCHER AND A BUNDLED INTERPRETER. The standard slots (Keystone's census --probe, the generator's
# host-launch) exec the instrument INSIDE each peer's own toolchain image, and no interpreter is common to those
# images. So the suite carries its own: a pinned python-build-standalone CPython (musl) plus the musl loader,
# invoked through the loader so the image's libc — glibc or musl — is never consulted. Measured 2026-09-13 on
# Keystone python/rust/node24/go, core-go and alpine, all --network=none.
#
# `env -i` because a peer image's PYTHONPATH / PYTHONHOME must not reach this interpreter. ADDR is passed through:
# the generator's CLIENT slot hands the address over in the environment.
B="$0.d"
[ -d "$B/pyrt" ] || { echo "s1-py: bundle not found at $B (run make build)" >&2; exit 3; }
exec env -i ADDR="${ADDR:-}" PYTHONHOME="$B/pyrt/python" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$B/pyrt/ld-musl-x86_64.so.1" --library-path "$B/pyrt/python/lib" \
  "$B/pyrt/python/bin/python3.12" -s -B "$B/suite/run.py" "$@"
