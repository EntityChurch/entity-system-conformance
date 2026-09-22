//! rs-conformance — suite 2 of the entity-core independent conformance instrument.
//!
//! Rust, std only, zero dependencies, static musl binary. Built against
//! `spec-data/entity-core-protocol/v0.8.2.26/` and the three ADR-0003-shaped requirement files.
//!
//! ⛔ WHAT THIS SUITE DID NOT READ, because that is the whole point of it existing:
//! `suites/py-prototype/**`, `suites/*/items/**`, `suites/CONTROL-SET.diag`,
//! `entity-core-go`'s `validate-peer`, and the 47 requirement files still carrying a fused probe
//! design. If this suite agrees with suite 1 it is because the protocol said so.

mod cbor;
mod checks;
mod ecf;
mod json;
mod sha256;
mod wire;

use checks::{CheckResult, Ctx, Verdict};
use json::{to_string, J};
use sha256::{hex, sha256};
use std::time::Duration;

// -------------------------------------------------------------------------------------------
// Provenance, embedded at BUILD time
//
// AGENTS.md's staleness rule: "Every verdict carries the sha256 of the obligation it was scored
// against, or it is not evidence." A requirement file moved twice in one day and three peers'
// PASS was against text that no longer existed. So the obligation bytes are compiled in and
// re-hashed at runtime — a rebuilt binary carries a new digest and a stale binary is detectable
// from its own output.
// -------------------------------------------------------------------------------------------
const R57_BYTES: &[u8] = include_bytes!("../../../requirements/entity-core-protocol/ECP-R57.diag");
const R3_BYTES: &[u8] = include_bytes!("../../../requirements/entity-core-protocol/ECP-R3.diag");
const R7_BYTES: &[u8] = include_bytes!("../../../requirements/entity-core-protocol/ECP-R7.diag");

// D16 / AP-13: the snapshot is DERIVED, never restated here. `build.rs` reads it out of the
// requirement files' own `snapshot` field, refuses to build if they disagree, and generates
// SNAPSHOT / SPEC_VERSION / SNAPSHOT_MANIFEST below. Nothing in `src/` names a snapshot.
include!(concat!(env!("OUT_DIR"), "/snapshot.rs"));

const SUITE_NAME: &str = "rs-conformance";
const SUITE_VERSION: &str = env!("CARGO_PKG_VERSION");

struct Args {
    addr: Option<String>,
    profile: String,
    json_out: Option<String>,
    posture_file: Option<String>,
    requirements: Option<Vec<String>>,
    allow_skip: Vec<String>,
    /// `--peer <label>` or `--peer <label>=<addr>`, repeatable. Contract §3: a cross-peer
    /// requirement names ROLES, and the verdict records WHICH two peers produced each result.
    /// None of this suite's three requirements is cross-peer yet, so today these are recorded as
    /// declared labels and nothing more — recorded rather than dropped, because a label the
    /// runner passed and the verdict never mentions is an input that decided nothing and proved
    /// it to no one.
    peers: Vec<String>,
    /// The grants string the LAUNCHER recorded (`make peer-up` writes it to output/peer-up.posture
    /// and passes it down). This is the founding rule of this seat working as intended: the
    /// posture is recorded by whatever started the peer, and the instrument reads that record
    /// instead of typing its own. Until 2026-09-13 this value was hand-typed downstream.
    posture_grants: Option<String>,
    list_requirements: bool,
    read_timeout_ms: u64,
    connect_timeout_ms: u64,
}

fn parse_args() -> Result<Args, String> {
    let mut a = Args {
        addr: None,
        profile: "core".into(),
        json_out: None,
        posture_file: None,
        requirements: None,
        allow_skip: vec![],
        peers: vec![],
        posture_grants: None,
        list_requirements: false,
        read_timeout_ms: 5000,
        connect_timeout_ms: 5000,
    };
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < argv.len() {
        // The runner slot is documented with SINGLE dashes (`-addr HOST:PORT -profile core
        // -json-out PATH`) and the contract document with double. Both are accepted; refusing
        // one would make this suite un-swappable for the sake of a spelling.
        let raw = argv[i].clone();
        let flag = raw.trim_start_matches('-').to_string();
        let next = |i: &mut usize| -> Result<String, String> {
            *i += 1;
            argv.get(*i)
                .cloned()
                .ok_or_else(|| format!("{} needs a value", raw))
        };
        match flag.as_str() {
            "addr" => a.addr = Some(next(&mut i)?),
            "profile" => a.profile = next(&mut i)?,
            "json-out" | "json_out" => a.json_out = Some(next(&mut i)?),
            "posture" => a.posture_file = Some(next(&mut i)?),
            "requirements" => {
                a.requirements = Some(next(&mut i)?.split(',').map(|s| s.trim().to_string()).collect())
            }
            "allow-skip" => {
                a.allow_skip = next(&mut i)?.split(',').map(|s| s.trim().to_string()).collect()
            }
            "peer" => a.peers.push(next(&mut i)?),
            "posture-grants" => a.posture_grants = Some(next(&mut i)?),
            "list-requirements" => a.list_requirements = true,
            "timeout-ms" => {
                a.read_timeout_ms = next(&mut i)?.parse().map_err(|e| format!("timeout-ms: {}", e))?
            }
            "connect-timeout-ms" => {
                a.connect_timeout_ms =
                    next(&mut i)?.parse().map_err(|e| format!("connect-timeout-ms: {}", e))?
            }
            "category" => {
                // Accepted and ignored with a loud note rather than silently: an unrecognised
                // scope flag that narrows nothing produces a run larger than the caller asked
                // for, reported under the caller's narrower label.
                let v = next(&mut i)?;
                eprintln!(
                    "rs-conformance: --category {} is not implemented; this suite implements 3 \
                     requirements and runs them all. Use --requirements to scope.",
                    v
                );
            }
            "h" | "help" => {
                print_help();
                std::process::exit(0);
            }
            other => return Err(format!("unknown flag `{}`", other)),
        }
        i += 1;
    }
    Ok(a)
}

fn print_help() {
    println!(
        "rs-conformance {} — suite 2, entity-core conformance instrument\n\
         \n\
         USAGE\n  rs-conformance -addr HOST:PORT -profile core -json-out PATH\n\
         \n\
         FLAGS\n\
         \x20 -addr HOST:PORT        the peer under test\n\
         \x20 -profile core|full     which requirement set (only `core` is implemented)\n\
         \x20 -json-out PATH         the verdict document; stdout if omitted\n\
         \x20 -posture FILE          the declared fixture posture (see below)\n\
         \x20 -posture-grants STR    the grants string the launcher recorded; goes in the verdict\n\
         \x20 -peer LABEL[=ADDR]     a declared counterparty label, repeatable\n\
         \x20 -requirements ID,ID    scope the run\n\
         \x20 -allow-skip ID,ID      intentional skips, declared\n\
         \x20 -list-requirements     what this suite implements, machine-readable\n\
         \x20 -timeout-ms N          per-read deadline (default 5000)\n\
         \n\
         POSTURE\n\
         \x20 Every verdict records the posture it ran in. With no -posture file this suite uses\n\
         \x20 its built-in `pre-handshake-floor` posture and says so in the document\n\
         \x20 (`posture.source = suite-builtin-default`). It never emits a verdict with no posture.\n",
        SUITE_VERSION
    );
}

struct Implemented {
    id: &'static str,
    obligation_bytes: &'static [u8],
    scoreable: bool,
    note: &'static str,
}

fn implemented() -> Vec<Implemented> {
    vec![
        Implemented {
            id: "ECP-R57",
            obligation_bytes: R57_BYTES,
            scoreable: true,
            note: "a frame whose envelope root is neither EXECUTE nor EXECUTE_RESPONSE is refused \
                   with a coded 400 invalid_request response",
        },
        Implemented {
            id: "ECP-R3",
            obligation_bytes: R3_BYTES,
            scoreable: true,
            note: "a received EXECUTE whose root entity's content_hash does not match its \
                   {type, data} is refused with a coded EXECUTE_RESPONSE. The (status, code) half \
                   is CONTESTED against the requirement file — see the `contested` block.",
        },
        Implemented {
            id: "ECP-R7",
            obligation_bytes: R7_BYTES,
            scoreable: false,
            note: "included entity hash validation. WITNESS ONLY — §1.8 item 1 (0.8.2.26) forbids \
                   a check asserting a refusal on an unreferenced `included` entry.",
        },
    ]
}

fn main() {
    // The codec is the instrument. A wrong codec and a wrong peer are indistinguishable in a
    // verdict, so both self-tests run before anything is sent and a failure is fatal.
    if let Err(e) = sha256::selftest() {
        eprintln!("rs-conformance: REFUSING TO RUN — {}", e);
        std::process::exit(2);
    }
    if let Err(e) = cbor::selftest() {
        eprintln!("rs-conformance: REFUSING TO RUN — {}", e);
        std::process::exit(2);
    }

    let args = match parse_args() {
        Ok(a) => a,
        Err(e) => {
            eprintln!("rs-conformance: {}", e);
            print_help();
            std::process::exit(2);
        }
    };

    if args.list_requirements {
        let rows: Vec<J> = implemented()
            .iter()
            .map(|r| {
                J::O(vec![
                    ("requirement_id".into(), J::s(r.id)),
                    ("snapshot".into(), J::s(SNAPSHOT)),
                    (
                        "obligation_digest".into(),
                        J::S(format!("sha256:{}", hex(&sha256(r.obligation_bytes)))),
                    ),
                    ("scoreable".into(), J::B(r.scoreable)),
                    ("note".into(), J::s(r.note)),
                ])
            })
            .collect();
        print!(
            "{}",
            to_string(&J::O(vec![
                ("suite".into(), J::s(SUITE_NAME)),
                ("version".into(), J::s(SUITE_VERSION)),
                ("profile".into(), J::s("core")),
                ("requirements".into(), J::A(rows)),
            ]))
        );
        return;
    }

    if args.profile != "core" {
        eprintln!(
            "rs-conformance: profile `{}` is not implemented; this suite implements `core` only. \
             Refusing rather than running core and labelling it `{}`.",
            args.profile, args.profile
        );
        std::process::exit(2);
    }

    let addr = match &args.addr {
        Some(a) => a.clone(),
        None => {
            eprintln!("rs-conformance: -addr HOST:PORT is required");
            print_help();
            std::process::exit(2);
        }
    };

    let ctx = Ctx {
        addr: addr.clone(),
        connect_timeout: Duration::from_millis(args.connect_timeout_ms),
        read_timeout: Duration::from_millis(args.read_timeout_ms),
    };

    let want = |id: &str| -> bool {
        match &args.requirements {
            Some(list) => list.iter().any(|x| x == id),
            None => true,
        }
    };

    let mut results: Vec<CheckResult> = Vec::new();
    if want("ECP-R57") {
        results.push(checks::check_r57(&ctx));
    }
    if want("ECP-R3") {
        results.push(checks::check_r3(&ctx));
    }
    if want("ECP-R7") {
        results.push(checks::check_r7(&ctx));
    }

    let doc = build_document(&args, &addr, &results);
    let text = to_string(&doc);

    match &args.json_out {
        Some(path) => {
            if let Err(e) = std::fs::write(path, &text) {
                eprintln!("rs-conformance: could not write {}: {}", path, e);
                std::process::exit(2);
            }
        }
        None => print!("{}", text),
    }

    // Human summary on stderr so it never contaminates a stdout verdict document.
    eprintln!("rs-conformance {} against {} @ {}", SUITE_VERSION, addr, SNAPSHOT);
    for r in &results {
        eprintln!(
            "  {:<7} {:<9} {:<48} {}",
            r.verdict.as_str(),
            r.requirement_id,
            r.suite_check,
            r.failure_mode.clone().unwrap_or_default()
        );
        if let Some(c) = &r.contested {
            eprintln!(
                "          ⚠ CONTESTED vs the requirement file: {} (under this suite's reading: {})",
                c.about,
                c.verdict_under_this_reading.as_str()
            );
        }
        if !r.control.held {
            eprintln!("          ⛔ control did not hold: {}", r.control.observed);
        }
    }
    // Exit 0 means "the instrument ran and produced a document", never "the peer passed".
    // Conflating those is how a failing run gets read as a green one.
}

fn build_document(args: &Args, addr: &str, results: &[CheckResult]) -> J {
    let impls = implemented();

    // The comparability anchor (contract §2): what was RUN, by content.
    let mut set_input = Vec::new();
    for r in results {
        if let Some(im) = impls.iter().find(|i| i.id == r.requirement_id) {
            set_input.extend_from_slice(im.id.as_bytes());
            set_input.push(b':');
            set_input.extend_from_slice(&sha256(im.obligation_bytes));
            set_input.push(b'\n');
        }
    }
    let requirement_set_digest = format!("sha256:{}", hex(&sha256(&set_input)));

    let mut summary = (0u64, 0u64, 0u64, 0u64, 0u64, 0u64); // total,pass,warn,fail,skip,attributable
    for r in results {
        summary.0 += 1;
        match r.verdict {
            Verdict::Pass => summary.1 += 1,
            Verdict::Warn => summary.2 += 1,
            Verdict::Fail => summary.3 += 1,
            Verdict::Skip => summary.4 += 1,
        }
        if r.peer_attributable {
            summary.5 += 1;
        }
    }

    let rows: Vec<J> = results
        .iter()
        .map(|r| {
            let obligation_digest = impls
                .iter()
                .find(|i| i.id == r.requirement_id)
                .map(|i| format!("sha256:{}", hex(&sha256(i.obligation_bytes))))
                .unwrap_or_else(|| "sha256:unknown".into());

            let mut fields = vec![
                ("requirement_id".into(), J::s(&r.requirement_id)),
                ("suite_check".into(), J::s(&r.suite_check)),
                ("verdict".into(), J::s(r.verdict.as_str())),
                ("spec_ref".into(), J::s(&r.spec_ref)),
                ("snapshot".into(), J::s(SNAPSHOT)),
                // AGENTS.md's staleness rule, per row.
                ("obligation_digest".into(), J::S(obligation_digest)),
                ("peer_attributable".into(), J::B(r.peer_attributable)),
                ("domain_member".into(), J::Null),
                (
                    "failure_mode".into(),
                    match &r.failure_mode {
                        Some(f) => J::s(f),
                        None => J::Null,
                    },
                ),
                ("observed".into(), J::s(&r.observed)),
                ("message".into(), J::s(&r.message)),
                (
                    "negative_control".into(),
                    J::O(vec![
                        ("name".into(), J::s(&r.control.name)),
                        ("held".into(), J::B(r.control.held)),
                        ("expectation".into(), J::s(&r.control.expectation)),
                        ("observed".into(), J::s(&r.control.observed)),
                    ]),
                ),
                (
                    "witness".into(),
                    J::O(r.witness.iter().map(|(k, v)| (k.clone(), J::s(v))).collect()),
                ),
            ];

            if let Some(c) = &r.contested {
                fields.push((
                    "contested".into(),
                    J::O(vec![
                        ("about".into(), J::s(&c.about)),
                        ("requirement_file_says".into(), J::s(&c.file_says)),
                        ("this_suite_reads".into(), J::s(&c.this_suite_reads)),
                        ("evidence".into(), J::s(&c.evidence)),
                        (
                            "verdict_under_this_reading".into(),
                            J::s(c.verdict_under_this_reading.as_str()),
                        ),
                        ("routed_as".into(), J::s(&c.routed_as)),
                    ]),
                ));
            }

            J::O(fields)
        })
        .collect();

    J::O(vec![
        (
            "suite".into(),
            J::O(vec![
                ("name".into(), J::s(SUITE_NAME)),
                ("version".into(), J::s(SUITE_VERSION)),
                ("language".into(), J::s("rust (std only, zero dependencies)")),
                (
                    "independence".into(),
                    J::s(
                        "SHA-256 from FIPS 180-4 and canonical CBOR from RFC 8949 §4.2 + ECF §4.1 \
                         are implemented in-tree. No crypto or codec library is linked, and no \
                         other instrument's source was read while authoring these checks.",
                    ),
                ),
            ]),
        ),
        (
            "spec".into(),
            J::O(vec![
                ("version".into(), J::s(SPEC_VERSION)),
                ("snapshot".into(), J::s(SNAPSHOT)),
                (
                    "snapshot_manifest_digest".into(),
                    J::S(format!("sha256:{}", hex(&sha256(SNAPSHOT_MANIFEST)))),
                ),
                (
                    "note".into(),
                    J::s(
                        "built against the pin deliberately — a measurement whose input nobody \
                         pinned is not a measurement. The snapshot is DERIVED from the \
                         requirement files' own `snapshot` field (D16), never restated in source, \
                         so a re-base cannot leave this field claiming text the run never saw.",
                    ),
                ),
            ]),
        ),
        ("profile".into(), J::s("core")),
        ("requirement_set_digest".into(), J::S(requirement_set_digest)),
        ("posture".into(), posture(args)),
        (
            "peers".into(),
            J::A(std::iter::once(J::O(vec![
                ("label".into(), J::s(args.peers.first().map(|p| p.split('=').next().unwrap_or("subject")).unwrap_or("subject"))),
                ("addr".into(), J::s(addr)),
                // ADR-0003 §7.3: a verdict records the peer's IDENTITY, not its name. This suite
                // cannot resolve one from the wire alone before the handshake completes, and says
                // so rather than writing a name into an identity field.
                ("peer_id".into(), J::Null),
                (
                    "identity_resolution".into(),
                    J::s(
                        "NOT RESOLVED. Every probe in this suite is pre-handshake, so no \
                         authenticated peer identity is available to record. The runner that \
                         launched the peer knows which bytes it launched; this instrument does \
                         not, and does not guess. An addr is not an identity.",
                    ),
                ),
                ("contract_certified".into(), J::B(false)),
            ]))
            .chain(args.peers.iter().skip(1).map(|p| {
                let (label, addr) = match p.split_once('=') {
                    Some((l, a)) => (l.to_string(), Some(a.to_string())),
                    None => (p.clone(), None),
                };
                J::O(vec![
                    ("label".into(), J::S(label)),
                    ("addr".into(), match addr { Some(a) => J::S(a), None => J::Null }),
                    ("peer_id".into(), J::Null),
                    (
                        "role".into(),
                        J::s(
                            "DECLARED BUT NOT DIALLED. None of this suite's three requirements is \
                             cross-peer, so no probe reached this peer. Recorded because a \
                             declared input that no artifact mentions is the undeclared-sample \
                             defect one level up.",
                        ),
                    ),
                    ("contract_certified".into(), J::B(false)),
                ])
            }))
            .collect()),
        ),
        (
            "summary".into(),
            J::O(vec![
                ("total".into(), J::N(summary.0)),
                ("passed".into(), J::N(summary.1)),
                ("warned".into(), J::N(summary.2)),
                ("failed".into(), J::N(summary.3)),
                ("skipped".into(), J::N(summary.4)),
                ("peer_attributable".into(), J::N(summary.5)),
                (
                    "accounting_note".into(),
                    J::s(
                        "a skip counts as a failure ([ADR-0012]). ECP-R7 is a SKIP that the \
                         SPECIFICATION forbids scoring, which is a different thing; it carries \
                         peer_attributable:false so it scores nobody.",
                    ),
                ),
            ]),
        ),
        (
            "declared_exclusions".into(),
            J::A(args.allow_skip.iter().map(|s| J::s(s)).collect()),
        ),
        ("results".into(), J::A(rows)),
    ])
}

/// §4 of the contract: the posture is a first-class input and a suite refuses to emit a verdict
/// without one. With no `-posture` file this suite emits its BUILT-IN posture and labels it as
/// such — the alternative, an absent field, is the exact defect this seat was founded on.
fn posture(args: &Args) -> J {
    let launcher_grants = args.posture_grants.clone();
    let (source, external) = match &args.posture_file {
        Some(p) => match std::fs::read_to_string(p) {
            Ok(body) => (
                format!("operator-supplied: {}", p),
                Some(format!("sha256:{}", hex(&sha256(body.as_bytes())))),
            ),
            Err(e) => (format!("operator-supplied {} UNREADABLE: {}", p, e), None),
        },
        None => ("suite-builtin-default".to_string(), None),
    };

    let mut fields = vec![
        ("name".into(), J::s("pre-handshake-floor")),
        ("source".into(), J::S(source)),
        ("connection_state".into(), J::s("not_established")),
        ("handshake_legs_completed".into(), J::N(0)),
        (
            "grants".into(),
            J::O(vec![
                (
                    "reached_by_these_probes".into(),
                    J::s(
                        "none. Every probe targets `system/protocol/connect`, which §4.2 makes the \
                         sole pre-authorized path in any connection state, so no grant \
                         participates in any refusal this suite observes.",
                    ),
                ),
                (
                    "launcher_recorded".into(),
                    match &launcher_grants {
                        Some(g) => J::S(g.clone()),
                        None => J::Null,
                    },
                ),
                (
                    "launcher_recorded_note".into(),
                    J::s(
                        "verbatim from whatever launched the peer, never re-typed here. ⚠ It is \
                         recorded EVEN THOUGH no probe in this run reaches a granted surface: two \
                         runs under different postures are not a better and a worse number, and a \
                         reader cannot establish that the posture was irrelevant unless the \
                         posture is in the document.",
                    ),
                ),
            ]),
        ),
        (
            "identities".into(),
            J::O(vec![
                ("author".into(), J::s("absent — §3.2 exempts the connection path")),
                ("capability".into(), J::s("absent — §3.2 exempts the connection path")),
                ("signature".into(), J::s("absent — no Ed25519 is used by this suite")),
            ]),
        ),
        (
            "transport".into(),
            J::s("raw TCP; §5.1 frames (4-byte big-endian length prefix + CBOR payload)"),
        ),
        (
            "connection_reuse".into(),
            J::s(
                "NONE — one fresh TCP connection per probe and per control. §4.11 (0.8.2.26) lets \
                 a peer bound consecutive pre-admission refusals on one connection as local \
                 policy, and a check set MUST NOT assert that bound or its absence; reusing a \
                 connection would measure the policy instead of the row.",
            ),
        ),
        (
            "negotiated_defaults".into(),
            J::O(vec![
                ("hash_formats".into(), J::s("field omitted; §4.5 default [\"ecfv1-sha256\"]")),
                ("key_types".into(), J::s("field omitted; §4.5 default [\"ed25519\"]")),
                ("protocols".into(), J::s("[\"entity-core/1.0\"] — §4.5 Required, no default")),
            ]),
        ),
        (
            "not_measured".into(),
            J::A(vec![
                J::s(
                    "THE ESTABLISHED-CONNECTION POSTURE. ECP-R57's requirement file states its \
                     subject is sent on an established connection. Reaching that state needs leg 2 \
                     of §4.1's handshake, which needs an Ed25519 signature this suite does not \
                     implement. So R57 is measured PRE-HANDSHAKE and that is declared here rather \
                     than assumed equivalent. §6.5's dispatch chain places the wrong-root-type arm \
                     at the same level as `Root is EXECUTE?` — i.e. BEFORE any connection-state \
                     branch — which is this suite's argument that the arm is state-independent; \
                     it is an argument, not a measurement, and the established-posture run is \
                     NOT TAKEN.",
                ),
                J::s(
                    "ECP-R7 over a REFERENCED included entry — the scoreable form §1.8 item 1 \
                     (0.8.2.26) leaves open. Not designed here.",
                ),
            ]),
        ),
        (
            "timeouts_ms".into(),
            J::O(vec![
                ("connect".into(), J::N(args.connect_timeout_ms)),
                ("read".into(), J::N(args.read_timeout_ms)),
                (
                    "why_it_is_posture".into(),
                    J::s(
                        "the read deadline is what separates §4.11's silent drop from a slow \
                         answer, so it decides a verdict and belongs in the declared posture",
                    ),
                ),
            ]),
        ),
    ];
    if let Some(d) = external {
        fields.push(("operator_posture_digest".into(), J::S(d)));
        fields.push((
            "operator_posture_applied".into(),
            J::s(
                "NO — the file's digest is recorded for traceability, but this suite does not yet \
                 interpret an external posture document. It does not silently claim to have \
                 applied one.",
            ),
        ));
    }
    J::O(fields)
}
