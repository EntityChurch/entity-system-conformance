//! The three checks, and their negative controls.
//!
//! ⛔ EVERY CHECK HERE IS DERIVED FROM `spec-data/entity-core-protocol/v0.8.2.26/` AND FROM THE
//! THREE PERMITTED REQUIREMENT FILES. No other instrument's source was read. Where this suite's
//! reading of the pinned text differs from a requirement file's stated conclusion, the
//! difference is emitted as data (`contested`), never silently resolved in either direction.

use crate::ecf::*;
use crate::json::base58;
use crate::sha256::{hex, sha256};
use crate::wire::{Conn, Frame, Outcome};
use std::time::Duration;

pub const EXECUTE_TYPE: &str = "system/protocol/execute";
pub const RESPONSE_TYPE: &str = "system/protocol/execute/response";

pub struct Ctx {
    pub addr: String,
    pub connect_timeout: Duration,
    pub read_timeout: Duration,
}

/// The contract's verdict vocabulary. `Warn` is unused today and is kept because the vocabulary
/// is the contract's, not this suite's — narrowing it here would make the document un-swappable.
#[allow(dead_code)]
#[derive(Debug, Clone, PartialEq)]
pub enum Verdict {
    Pass,
    Warn,
    Fail,
    Skip,
}

impl Verdict {
    pub fn as_str(&self) -> &'static str {
        match self {
            Verdict::Pass => "PASS",
            Verdict::Warn => "WARN",
            Verdict::Fail => "FAIL",
            Verdict::Skip => "SKIP",
        }
    }
}

pub struct CheckResult {
    pub requirement_id: String,
    pub suite_check: String,
    pub spec_ref: String,
    pub verdict: Verdict,
    pub peer_attributable: bool,
    /// §4.11's named failures are DISTINCT. This field is what keeps them distinct in the
    /// verdict document; a consumer that reads only `verdict` gets the top line right and learns
    /// nothing, which is precisely the error this suite was told to avoid.
    pub failure_mode: Option<String>,
    pub observed: String,
    pub witness: Vec<(String, String)>,
    pub control: ControlResult,
    pub message: String,
    /// Present where this suite's reading of the pinned snapshot and the requirement file's
    /// stated conclusion do not agree. A disagreement is the product; burying it is not an option
    /// and silently acting on it unilaterally is not either.
    pub contested: Option<Contested>,
}

pub struct Contested {
    pub about: String,
    pub file_says: String,
    pub this_suite_reads: String,
    pub evidence: String,
    pub verdict_under_this_reading: Verdict,
    pub routed_as: String,
}

pub struct ControlResult {
    pub held: bool,
    pub name: String,
    pub expectation: String,
    pub observed: String,
}

fn describe(o: &Outcome) -> String {
    match o {
        Outcome::Frame(f) => format!(
            "frame root={} status={} code={} request_id={} closed_after={} tag_in_answer={}",
            f.root_type,
            f.status.map(|s| s.to_string()).unwrap_or("-".into()),
            f.code.clone().unwrap_or("-".into()),
            f.request_id.clone().unwrap_or("-".into()),
            f.closed_after,
            f.answer_carried_tag
        ) + &f
            .message
            .as_deref()
            .map(|m| format!(" message={:?}", m))
            .unwrap_or_default(),
        Outcome::Unreadable { bytes, why } => format!("unreadable answer ({} bytes): {}", bytes, why),
        Outcome::BareClose => "bare close: socket closed with no frame on it".into(),
        Outcome::SilentDrop => "silent drop: no frame and no close before the deadline".into(),
        Outcome::Unreachable(e) => format!("unreachable: {}", e),
    }
}

/// A peer id that satisfies §5.4's `is_peer_id` (>= 46 Base58 characters, Base58 alphabet only).
/// Derived, not random, so two runs of this suite send the same probe bytes.
fn probe_peer_id() -> String {
    let digest = sha256(b"entity-system-conformance/rs-conformance/probe-identity/v1");
    // §5.4: Base58(key_type || hash_type || digest). 0x01,0x00 chosen non-zero-leading so the
    // encoding does not shorten below the 46-character floor.
    let mut raw = vec![0x01u8, 0x00];
    raw.extend_from_slice(&digest);
    let id = base58(&raw);
    debug_assert!(id.len() >= 46, "probe peer_id below the §5.4 floor");
    id
}

fn probe_nonce(tag: &str) -> Vec<u8> {
    // §3.8: nonce is random(32). Derived deterministically so probes are reproducible — the
    // nonce's randomness matters to the handshake's replay properties, which no probe here
    // reaches, and reproducibility matters to every verdict this suite emits.
    sha256(format!("rs-conformance/nonce/{}", tag).as_bytes()).to_vec()
}

fn valid_hello_envelope(tag: &str) -> Envelope {
    let hello = hello_entity(&probe_peer_id(), &probe_nonce(tag), 1_737_900_000_000);
    Envelope::new(hello_execute(&format!("rsc-{}", tag), hello))
}

// ---------------------------------------------------------------------------------------------
// The negative control
// ---------------------------------------------------------------------------------------------

/// Send the SAME input with the one thing under test CORRECTED, and confirm the peer answers.
///
/// ⛔ The bar here is deliberately narrow, and it is narrow because of a named incident: a
/// control that accepts "any response" accepts the exact refusal that must VOID the probe, and
/// then a peer which refuses everything passes every probe in the suite. So the control holds
/// ONLY on an affirmative answer: an EXECUTE_RESPONSE with a 2xx status. A 4xx, a close, a
/// silence, an unreadable answer and an unreachable peer all VOID.
fn run_control(ctx: &Ctx, name: &str, env: &Envelope) -> ControlResult {
    let expectation = format!(
        "a {} with a 2xx status — the corrected input is a well-formed hello and §4.1 says the \
         responder replies with its own hello data",
        RESPONSE_TYPE
    );

    let outcome = match Conn::open(&ctx.addr, ctx.connect_timeout, ctx.read_timeout) {
        Ok(mut c) => c.exchange(&env.to_frame()),
        Err(e) => Outcome::Unreachable(e),
    };

    let observed = describe(&outcome);

    let held = match &outcome {
        Outcome::Frame(f) => {
            let right_type = f.root_type == RESPONSE_TYPE;
            let affirmative = matches!(f.status, Some(s) if (200..300).contains(&s));
            right_type && affirmative
        }
        // Every one of these is a VOID, spelled out rather than left to a catch-all, so that
        // adding a new Outcome variant later cannot silently fall into "control held".
        Outcome::Unreadable { .. } => false,
        Outcome::BareClose => false,
        Outcome::SilentDrop => false,
        Outcome::Unreachable(_) => false,
    };

    ControlResult {
        held,
        name: name.to_string(),
        expectation,
        observed,
    }
}

fn voided(
    requirement_id: &str,
    suite_check: &str,
    spec_ref: &str,
    control: ControlResult,
) -> CheckResult {
    let msg = format!(
        "COULD NOT LOOK. The negative control did not hold, so nothing this probe observes is \
         attributable to the requirement. Control expected: {}. Control observed: {}. \
         A skip counts as a failure ([ADR-0012]); this is not a pass.",
        control.expectation, control.observed
    );
    CheckResult {
        requirement_id: requirement_id.into(),
        suite_check: suite_check.into(),
        spec_ref: spec_ref.into(),
        verdict: Verdict::Skip,
        // The peer is not scored on a probe we could not attribute.
        peer_attributable: false,
        failure_mode: Some("control_void".into()),
        observed: "probe not sent — control failed first".into(),
        witness: vec![],
        control,
        message: msg,
        contested: None,
    }
}

// ---------------------------------------------------------------------------------------------
// ECP-R57 — a frame whose root is neither EXECUTE nor EXECUTE_RESPONSE
// ---------------------------------------------------------------------------------------------

/// §3.3 (final paragraph), §4.11 (cause table, fifth row), §6.5 ("Other type?").
///
/// The obligation, at 0.8.2.26: a coded `400 invalid_request` EXECUTE_RESPONSE goes on the wire.
/// The close is the peer's own choice and is NOT evidence of anything.
///
/// The two non-conformant shapes — dropping the frame, and closing with no coded frame — are
/// named by §4.11 as "distinct failures rather than one" and are scored separately here.
pub fn check_r57(ctx: &Ctx) -> CheckResult {
    let id = "ECP-R57";
    let name = "connectivity/r57_wrong_root_message_type";
    let spec_ref = "ENTITY-CORE-PROTOCOL §3.3 (final paragraph); §4.11 cause table row 5; §6.5";

    // Control: the SAME envelope shape with the ONE thing under test corrected — the root's type.
    let control = run_control(ctx, "r57_control_correct_root_type", &valid_hello_envelope("r57c"));
    if !control.held {
        return voided(id, name, spec_ref, control);
    }

    // Probe: canonical, correctly framed, correctly self-hashed, no CBOR tag. The ONLY defect is
    // that `root.type` is neither EXECUTE nor EXECUTE_RESPONSE.
    let root = wrong_root_entity();
    // Guard the premise of the whole check rather than trusting the constructor. If the subject's
    // type were ever edited to one of the two wire message types, this probe would be measuring
    // an entirely different row while still producing a plausible-looking verdict.
    if root.ty == EXECUTE_TYPE || root.ty == RESPONSE_TYPE {
        return voided(
            id,
            name,
            spec_ref,
            ControlResult {
                held: false,
                name: "r57_subject_premise".into(),
                expectation: format!("subject root type is neither {} nor {}", EXECUTE_TYPE, RESPONSE_TYPE),
                observed: format!("subject root type is `{}` — the probe is invalid", root.ty),
            },
        );
    }
    let env = Envelope::new(root);
    let outcome = match Conn::open(&ctx.addr, ctx.connect_timeout, ctx.read_timeout) {
        Ok(mut c) => c.exchange(&env.to_frame()),
        Err(e) => Outcome::Unreachable(e),
    };
    let observed = describe(&outcome);
    let mut witness = vec![
        (
            "probe_root_type".into(),
            "primitive/any (well-formed, canonical, self-consistent hash, no tag)".into(),
        ),
        (
            "request_id_available_to_peer".into(),
            // §4.11 permits a best-effort UNCORRELATED frame where no id is available. This
            // probe's root carries no request_id at all, so correlation MUST NOT be asserted.
            "no — the root is not an EXECUTE and carries no request_id; §4.11's best-effort \
             uncorrelated frame is conformant here and correlation is NOT asserted"
                .into(),
        ),
    ];

    let (verdict, failure_mode, message) = match &outcome {
        Outcome::Frame(f) => {
            witness.push(("observed_status".into(), f.status.map(|s| s.to_string()).unwrap_or("absent".into())));
            witness.push(("observed_code".into(), f.code.clone().unwrap_or("absent".into())));
            witness.push(("closed_after_answer".into(), f.closed_after.to_string()));
            classify_coded(f, 400, "invalid_request", id)
        }
        Outcome::BareClose => (
            Verdict::Fail,
            Some("bare_close".into()),
            "§4.11's SECOND named failure: the peer closed with no coded frame. Indistinguishable \
             from a network fault (§4.6). Scored SEPARATELY from a silent drop — the two remedies \
             are opposite."
                .into(),
        ),
        Outcome::SilentDrop => (
            Verdict::Fail,
            Some("silent_drop".into()),
            "§4.11's FIRST named failure: no response and no close. The caller learns nothing \
             until its own §6.11(c) deadline and the refusal is unobservable. Scored SEPARATELY \
             from a bare close."
                .into(),
        ),
        Outcome::Unreadable { why, .. } => (
            Verdict::Fail,
            Some("unreadable_answer".into()),
            format!(
                "the peer answered, and the answer is not a readable envelope: {}. This is \
                 neither of §4.11's two named failures and is recorded as its own mode.",
                why
            ),
        ),
        Outcome::Unreachable(e) => (
            Verdict::Skip,
            Some("unreachable".into()),
            format!("COULD NOT LOOK: {}. Not a pass.", e),
        ),
    };

    CheckResult {
        requirement_id: id.into(),
        suite_check: name.into(),
        spec_ref: spec_ref.into(),
        peer_attributable: !matches!(outcome, Outcome::Unreachable(_)),
        verdict,
        failure_mode,
        observed,
        witness,
        control,
        message,
        contested: None,
    }
}

/// Shared classifier for "a coded pre-admission refusal with a PINNED code".
/// Kept here rather than inlined three times so the two failure modes cannot drift apart between
/// checks — but note it is shared WITHIN this suite only. No assertion is shared with any other
/// suite (AGENTS.md: sharing the substrate is fine; sharing assertions is not).
fn classify_coded(
    f: &Frame,
    want_status: u64,
    want_code: &str,
    id: &str,
) -> (Verdict, Option<String>, String) {
    if f.root_type != RESPONSE_TYPE {
        return (
            Verdict::Fail,
            Some("wrong_response_root_type".into()),
            format!(
                "{}: the peer answered with a frame whose root type is `{}`, not `{}`. §3.3: \
                 these are the only two wire message types.",
                id, f.root_type, RESPONSE_TYPE
            ),
        );
    }
    match (f.status, f.code.as_deref()) {
        (Some(s), Some(c)) if s == want_status && c == want_code => (
            Verdict::Pass,
            None,
            format!(
                "{}: coded EXECUTE_RESPONSE on the wire carrying {} {}. §4.11's frame obligation \
                 is met and the code matches the cause. The peer {} the connection afterwards, \
                 which §4.11 makes its own choice and which is NOT scored.",
                id,
                s,
                c,
                if f.closed_after { "closed" } else { "kept open" }
            ),
        ),
        (Some(s), c) if (200..300).contains(&s) => (
            Verdict::Fail,
            Some("request_admitted".into()),
            format!(
                "{}: the peer answered {} {} — the frame was processed rather than refused.",
                id,
                s,
                c.unwrap_or("(no code)")
            ),
        ),
        (Some(s), Some(c)) => (
            Verdict::Fail,
            Some("coded_response_wrong_code".into()),
            format!(
                "{}: the peer refused with a coded frame — so §4.11's FRAME obligation is met — \
                 but answered {} `{}` where the cause pins {} `{}`. §4.11: \"the code selects the \
                 caller's remedy, so a code that is merely in the right family is still wrong.\"",
                id, s, c, want_status, want_code
            ),
        ),
        (Some(s), None) => (
            Verdict::Fail,
            Some("coded_response_no_code".into()),
            format!(
                "{}: the peer answered status {} with no `result.data.code`. §3.3's default-code \
                 force makes the code mandatory for the generic case at that status.",
                id, s
            ),
        ),
        (None, _) => (
            Verdict::Fail,
            Some("response_without_status".into()),
            format!(
                "{}: an EXECUTE_RESPONSE arrived carrying no `status` field (§3.3).",
                id
            ),
        ),
    }
}

// ---------------------------------------------------------------------------------------------
// ECP-R3 — root entity hash validation
// ---------------------------------------------------------------------------------------------

/// §1.8 item 1, §7.2 (NORMATIVE), §6.5 ("Validate root entity hash"), §4.11, §5.2a.
///
/// ⭐ THIS CHECK CARRIES A DISAGREEMENT WITH ITS OWN REQUIREMENT FILE, AND EMITS IT AS DATA.
///
/// `ECP-R3.diag`'s reading concludes: "ANY status and code satisfies this file; the FRAME is what
/// is asserted", on the argument that §4.11's cause table has no root-hash row "by arch's
/// deliberate design" and that §1.8/§7.2 assign no code.
///
/// Read against the PINNED snapshot the file itself declares (v0.8.2.26), that argument does not
/// hold — see `Contested` below. So this check scores the half both readings agree on (the frame
/// obligation) and reports the code half as a contested observation rather than acting on it
/// unilaterally. Prohibition 2: we state what the spec requires; we do not decide it.
pub fn check_r3(ctx: &Ctx) -> CheckResult {
    let id = "ECP-R3";
    let name = "encoding/r3_root_entity_hash_mismatch";
    let spec_ref =
        "ENTITY-CORE-PROTOCOL §1.8 item 1; §7.2 (NORMATIVE); §6.5 dispatch chain; §4.11; §5.2a";

    // Control: the SAME hello with the ONE thing under test corrected — a truthful root hash.
    let control = run_control(ctx, "r3_control_correct_root_hash", &valid_hello_envelope("r3c"));
    if !control.held {
        return voided(id, name, spec_ref, control);
    }

    // Probe: a hello whose ROOT entity's carried content_hash differs from
    // SHA-256(ECF({type,data})) by exactly one bit. Everything else is correct: canonical CBOR,
    // correct framing, no tag, a valid `included`-free envelope, and a connection-path EXECUTE
    // that needs no author, no capability and no signature (§3.2, §4.2) — so a refusal is
    // attributable to the hash and to no posture.
    let hello = hello_entity(&probe_peer_id(), &probe_nonce("r3"), 1_737_900_000_000);
    let exec = hello_execute("rsc-r3", hello).with_corrupted_hash();
    let true_hash = exec.true_hash();
    let env = Envelope::new(exec.clone());

    let outcome = match Conn::open(&ctx.addr, ctx.connect_timeout, ctx.read_timeout) {
        Ok(mut c) => c.exchange(&env.to_frame()),
        Err(e) => Outcome::Unreachable(e),
    };
    let observed = describe(&outcome);

    let mut witness = vec![
        ("probe_defect".into(), "root entity content_hash differs from SHA-256(ECF({type,data})) by one bit".into()),
        ("root_true_hash".into(), hex(&true_hash)),
        ("root_carried_hash".into(), hex(&exec.carried_hash)),
        (
            "posture_confound".into(),
            "none — §3.2/§4.2 exempt the connection path from author and capability, so no grant, \
             identity or signature participates in this refusal"
                .into(),
        ),
    ];

    let mut contested = None;

    let (verdict, failure_mode, message) = match &outcome {
        Outcome::Frame(f) => {
            witness.push(("observed_status".into(), f.status.map(|s| s.to_string()).unwrap_or("absent".into())));
            witness.push(("observed_code".into(), f.code.clone().unwrap_or("absent".into())));
            witness.push(("closed_after_answer".into(), f.closed_after.to_string()));
            witness.push((
                "correlated_by_request_id".into(),
                // §4.11 asks for correlation "where the id is available". Whether an id inside a
                // frame the peer refused before reading its data counts as available is a real
                // open question, so it is witnessed and NOT scored.
                format!(
                    "{} (WITNESSED, NOT SCORED — §4.11 says 'where the id is available', and \
                     whether an id inside a frame refused at hash-validation time is 'available' \
                     is not settled by the pinned text)",
                    f.request_id.clone().unwrap_or("absent".into())
                ),
            ));

            // --- the half both readings agree on: the FRAME obligation ---
            let scored = if f.root_type != RESPONSE_TYPE {
                (
                    Verdict::Fail,
                    Some("wrong_response_root_type".into()),
                    format!("ECP-R3: answer root type `{}`, not `{}`.", f.root_type, RESPONSE_TYPE),
                )
            } else if matches!(f.status, Some(s) if (200..300).contains(&s)) {
                (
                    Verdict::Fail,
                    Some("hello_answered".into()),
                    "ECP-R3: THE FAILURE THE ROW EXISTS FOR. The peer answered the hello with a \
                     2xx, so the root entity was processed without its content_hash being \
                     validated. §1.8 item 1 and §7.2 both end in REJECT; §6.5 places the check \
                     first after decode."
                        .into(),
                )
            } else if f.status.is_some() {
                (
                    Verdict::Pass,
                    None,
                    "ECP-R3: a coded EXECUTE_RESPONSE refusal went on the wire. §4.11's FRAME \
                     obligation is met — and §4.11 (0.8.2.26) confirms this cause is a member of \
                     the class even though its cause has no row in the table. The (status, code) \
                     is CONTESTED; see `contested`."
                        .into(),
                )
            } else {
                (
                    Verdict::Fail,
                    Some("response_without_status".into()),
                    "ECP-R3: an EXECUTE_RESPONSE arrived carrying no `status` (§3.3).".into(),
                )
            };

            // --- the contested half: is a CODE pinned for this cause at 0.8.2.26? ---
            let code_ok = matches!((f.status, f.code.as_deref()), (Some(400), Some("hash_mismatch")));
            contested = Some(Contested {
                about: "whether the pinned snapshot assigns a (status, code) to a root-entity \
                        content_hash mismatch".into(),
                file_says:
                    "requirements/entity-core-protocol/ECP-R3.diag `reading`: \"ANY status and code \
                     satisfies this file; the FRAME is what is asserted\" — on the argument that \
                     §4.11's cause table has no root-hash row \"by arch's deliberate design\" and \
                     that §1.8/§7.2 assign no code."
                        .into(),
                this_suite_reads:
                    "the pinned v0.8.2.26 DOES assign one: 400 `hash_mismatch`. The file's premise \
                     is contradicted by §4.11's own 0.8.2.26 parenthetical, and its conclusion is \
                     contradicted by §6.5."
                        .into(),
                evidence:
                    "(1) §6.5 dispatch chain, verbatim: `+- Validate root entity hash | -> 400 \
                     hash_mismatch, coded frame; MAY then close (§4.11, §5.2a)`. That is the code, \
                     assigned to this exact arm, in the declared snapshot. \
                     (2) §4.11 (0.8.2.26): \"A cause absent from this table is a cause whose code \
                     is assigned by its own section\" — and §6.5 is that section. \
                     (3) §4.11's own rationale states the omission was NOT deliberate: \"a \
                     corrupted root-entity-hash refusal meets the class definition verbatim while \
                     appearing in no row, and four peers were measured bare-closing or silently \
                     dropping it while scoring PASS, because AN OMISSION FROM AN ENUMERATION IS \
                     INDISTINGUISHABLE FROM A DELIBERATE SCOPE LIMIT.\" The file asserts exactly \
                     the scope limit that sentence says cannot be inferred. \
                     (4) §5.2a corollary 1's .25 scoping does NOT carve the root out: it excludes \
                     \"bytes that were never hashed\", and defines those in the same sentence as \
                     \"a frame that does not decode into an Envelope at all\". This probe's frame \
                     decodes, and its bytes were hashed."
                        .into(),
                verdict_under_this_reading: if code_ok { Verdict::Pass } else { Verdict::Fail },
                routed_as:
                    "a requirement-file defect for this repo AND a question for the architecture \
                     seat: confirm §6.5's assignment is normative for this cause and add the row \
                     to §4.11's table. NOT resolved here — prohibition 2."
                        .into(),
            });

            scored
        }
        Outcome::BareClose => (
            Verdict::Fail,
            Some("bare_close".into()),
            "ECP-R3: §4.11's SECOND named failure — closed with no coded frame. \
             ⚠ ECP-R3.diag records that this outcome was ACCEPTED by suite 1 until 2026-09-16 \
             (F77). It is scored SEPARATELY from a silent drop."
                .into(),
        ),
        Outcome::SilentDrop => (
            Verdict::Fail,
            Some("silent_drop".into()),
            "ECP-R3: §4.11's FIRST named failure — no response and no close.".into(),
        ),
        Outcome::Unreadable { why, .. } => (
            Verdict::Fail,
            Some("unreadable_answer".into()),
            format!("ECP-R3: the peer answered unreadably: {}", why),
        ),
        Outcome::Unreachable(e) => (
            Verdict::Skip,
            Some("unreachable".into()),
            format!("COULD NOT LOOK: {}. Not a pass.", e),
        ),
    };

    CheckResult {
        requirement_id: id.into(),
        suite_check: name.into(),
        spec_ref: spec_ref.into(),
        peer_attributable: !matches!(outcome, Outcome::Unreachable(_)),
        verdict,
        failure_mode,
        observed,
        witness,
        control,
        message,
        contested,
    }
}

// ---------------------------------------------------------------------------------------------
// ECP-R7 — included entity hash validation. WITNESS ONLY.
// ---------------------------------------------------------------------------------------------

/// §3.1 ("Wire transport optimization"), §1.8 item 1, §6.5.
///
/// ⛔ NOT SCOREABLE, AND THE SPEC IS WHY. §1.8 item 1 at 0.8.2.26, verbatim:
///
///   "A uniform verdict on an UNREFERENCED `included` entry is mechanism-shaped and MUST NOT be
///    required [MUST] (0.8.2.26). ... A conformance check MUST NOT assert a refusal on this
///    input: asserting one votes mechanism (a) and makes (b) — which this item blesses —
///    unimplementable."
///
/// This probe's entry is unreferenced BY DESIGN (that is how §3.1's "each" is reached rather than
/// the weaker "each one the handler uses"), so the check observes and records and emits NO
/// verdict about the peer. `peer_attributable` is false and the row scores nobody.
pub fn check_r7(ctx: &Ctx) -> CheckResult {
    let id = "ECP-R7";
    let name = "encoding/r7_included_entity_hash_mismatch_unreferenced";
    let spec_ref = "ENTITY-CORE-PROTOCOL §3.1 (Wire transport optimization); §1.8 item 1; §6.5";

    // The control still runs: an observation taken against a peer that refuses everything is not
    // an observation, even when nothing is being scored.
    let mut control_env = valid_hello_envelope("r7c");
    let good = bystander_entity(1);
    control_env = control_env.with_included(good.true_hash(), good);
    let control = run_control(ctx, "r7_control_wellformed_included_entry", &control_env);
    if !control.held {
        return voided(id, name, spec_ref, control);
    }

    // Probe: a well-formed hello carrying one `included` entity the hello has no use for, whose
    // carried content_hash and map key both equal the hash of its ORIGINAL data, after which the
    // data was changed. Per ECP-R7.diag's reading of §1.8 item 1 mechanism (a): the entry is
    // both self-inconsistent and mis-keyed.
    let original = bystander_entity(1);
    let key = original.true_hash();
    let mutated = original
        .clone()
        .with_mutated_data(crate::cbor::Value::Map(vec![(
            crate::cbor::Value::text("m"),
            crate::cbor::Value::U64(2),
        )]));

    let hello = hello_entity(&probe_peer_id(), &probe_nonce("r7"), 1_737_900_000_000);
    let env = Envelope::new(hello_execute("rsc-r7", hello)).with_included(key.clone(), mutated.clone());

    let outcome = match Conn::open(&ctx.addr, ctx.connect_timeout, ctx.read_timeout) {
        Ok(mut c) => c.exchange(&env.to_frame()),
        Err(e) => Outcome::Unreachable(e),
    };
    let observed = describe(&outcome);

    let mut witness = vec![
        ("scoreability".into(), "NOT SCOREABLE — §1.8 item 1 (0.8.2.26) forbids a check asserting a refusal on an unreferenced `included` entry".into()),
        ("entry_referenced_by_root".into(), "no — by design; this is what makes the row unscoreable".into()),
        ("map_key".into(), hex(&key)),
        ("entry_carried_hash".into(), hex(&mutated.carried_hash)),
        ("entry_true_hash".into(), hex(&mutated.true_hash())),
    ];
    match &outcome {
        Outcome::Frame(f) => {
            witness.push(("observed_status".into(), f.status.map(|s| s.to_string()).unwrap_or("absent".into())));
            witness.push(("observed_code".into(), f.code.clone().unwrap_or("absent".into())));
            witness.push(("observed_shape".into(), "coded_response".into()));
            witness.push(("closed_after_answer".into(), f.closed_after.to_string()));
        }
        Outcome::BareClose => witness.push(("observed_shape".into(), "bare_close".into())),
        Outcome::SilentDrop => witness.push(("observed_shape".into(), "silent_drop".into())),
        Outcome::Unreadable { why, .. } => {
            witness.push(("observed_shape".into(), format!("unreadable: {}", why)))
        }
        Outcome::Unreachable(e) => witness.push(("observed_shape".into(), format!("unreachable: {}", e))),
    }

    CheckResult {
        requirement_id: id.into(),
        suite_check: name.into(),
        spec_ref: spec_ref.into(),
        verdict: Verdict::Skip,
        peer_attributable: false,
        failure_mode: Some("not_scoreable_by_spec".into()),
        observed,
        witness,
        control,
        message:
            "WITNESS ONLY, and this is a ruling rather than a limitation of this suite. §1.8 item 1 \
             (0.8.2.26) states that a uniform verdict on an unreferenced `included` entry is \
             mechanism-shaped and that a conformance check MUST NOT assert a refusal on it. The \
             observation is recorded and scores nobody. ⚠ This row is SKIP because the suite \
             contract's verdict vocabulary (PASS|WARN|FAIL|SKIP) has no value meaning \"observed, \
             not scoreable\" — and a SKIP counts as a failure under [ADR-0012], which is the wrong \
             accounting for a row the SPECIFICATION forbids scoring. Reported as a contract gap; \
             `peer_attributable: false` is the only thing keeping it from scoring the peer."
                .into(),
        contested: None,
    }
}
