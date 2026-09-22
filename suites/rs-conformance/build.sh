#!/bin/sh
# Build rs-conformance and install it into the runner's slot.
#
#   suites/rs-conformance/build.sh
#
# This suite is NOT built by the repo Makefile and should not be: that Makefile builds exactly one
# instrument (suite 1's bundled interpreter), and any other suite is DELIVERED as an executable.
#
# WHY A STATIC musl BINARY. The standard runner slots exec the instrument INSIDE each peer's own
# toolchain image, where no interpreter and no particular libc is guaranteed. Suite 1 solves that
# by bundling an entire pinned CPython plus a musl loader. A static binary just runs. This is the
# problem that sank the first attempt at packaging, so it is solved before any check was written.
#
# WHY CARGO_TARGET_DIR IS MOVED OUT OF THE SUITE TREE. `tools/suite-constants-gate.py` (D16)
# walks every `.rs` under `suites/` with no exclusion for build output, and `build.rs` legitimately
# GENERATES a file naming the snapshot it derived. Left under `suites/rs-conformance/target/` that
# generated file trips the gate — a false finding against the one mechanism that satisfies the
# rule. Building into the gitignored `output/` keeps source and artifact apart. (Reported: the
# gate has no build-artifact exclusion, which no Python suite could have surfaced.)

set -eu

SUITE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO=$(CDPATH= cd -- "$SUITE_DIR/../.." && pwd)
NAME=rs-conformance
TARGET=${TARGET:-x86_64-unknown-linux-musl}

CARGO_TARGET_DIR="$REPO/output/build/$NAME"
export CARGO_TARGET_DIR

if ! command -v cargo >/dev/null 2>&1; then
    echo "REFUSING — cargo is not on PATH. This suite is Rust; see suites/$NAME/README.md." >&2
    exit 2
fi

if ! rustc --print target-list 2>/dev/null | grep -qx "$TARGET" \
   || ! rustc --target "$TARGET" --print sysroot >/dev/null 2>&1; then
    :
fi

echo "building $NAME for $TARGET (zero dependencies, offline)"
cargo build --release --manifest-path "$SUITE_DIR/Cargo.toml" --target "$TARGET" --offline

BIN="$CARGO_TARGET_DIR/$TARGET/release/$NAME"
test -x "$BIN" || { echo "REFUSING — cargo reported success but $BIN is absent." >&2; exit 2; }

# Refuse to install a dynamically linked instrument: it would work here and fail inside a peer's
# image, and the failure would arrive as an unexplained empty run rather than as a build error.
# Tested for the DEFECT ("dynamically linked") rather than for one spelling of health: a static
# musl build reports "static-pie linked" here and "statically linked" elsewhere, and a guard
# matching one spelling refuses a good binary while a guard matching the other passes a bad one.
if command -v file >/dev/null 2>&1; then
    DESC=$(file -- "$BIN")
    case "$DESC" in
        *"dynamically linked"*|*"interpreter /lib"*)
            echo "REFUSING — this instrument is dynamically linked. The runner execs it inside" >&2
            echo "each peer's own image; a dynamic binary fails there and the failure arrives as" >&2
            echo "a missing result rather than as an error. Build for a musl target." >&2
            echo "$DESC" >&2
            exit 2
            ;;
    esac
fi
if command -v ldd >/dev/null 2>&1; then
    if ldd "$BIN" 2>&1 | grep -qv "statically linked\|not a dynamic executable"; then
        echo "REFUSING — ldd reports shared-object dependencies:" >&2
        ldd "$BIN" >&2
        exit 2
    fi
fi

mkdir -p "$REPO/output/bin"
install -m 0755 "$BIN" "$REPO/output/bin/$NAME"

# The instrument refuses to run if its own codec self-tests fail; prove that path works here
# rather than discovering it inside a peer container.
"$REPO/output/bin/$NAME" --list-requirements >/dev/null

echo "installed $REPO/output/bin/$NAME"
"$REPO/output/bin/$NAME" --list-requirements | sed -n '1,6p'
