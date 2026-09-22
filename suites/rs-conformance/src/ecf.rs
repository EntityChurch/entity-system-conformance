//! Entities, envelopes and content hashes, built from ENTITY-CBOR-ENCODING §4.2/§4.5/§5.3 and
//! ENTITY-CORE-PROTOCOL §3.1/§3.1.1/§3.2/§3.8.
//!
//! Every construction here is derived from the pinned snapshot's text, not from any other
//! instrument's source.

use crate::cbor::{encode, Value};
use crate::sha256::sha256;

/// §4.3 hash format registry, code 0x00 = ecfv1-sha256. The only Active entry.
pub const FMT_ECFV1_SHA256: u8 = 0x00;

/// content_hash = SHA-256(ECF({type, data}))   — ENTITY-CBOR-ENCODING §4.2.
///
/// The hashed map is `{"data": ..., "type": ...}` and nothing else. `content_hash` itself is
/// explicitly NOT hashed (§4.2 "What is NOT hashed").
pub fn content_hash_bytes(ty: &str, data: &Value) -> Vec<u8> {
    let basis = Value::Map(vec![
        (Value::text("data"), data.clone()),
        (Value::text("type"), Value::text(ty)),
    ]);
    let digest = sha256(&encode(&basis));
    // §4.5 hash wire encoding: format-code || digest.
    let mut out = Vec::with_capacity(33);
    out.push(FMT_ECFV1_SHA256);
    out.extend_from_slice(&digest);
    out
}

/// An entity as it appears on the wire (§5.3): {"type", "data", "content_hash"}.
///
/// `content_hash` is carried SEPARATELY from {type,data} rather than derived at encode time,
/// because the probes in this suite need to author an entity whose carried hash is deliberately
/// not the hash of its content. A builder that always recomputed could not express ECP-R3.
#[derive(Clone)]
pub struct Entity {
    pub ty: String,
    pub data: Value,
    pub carried_hash: Vec<u8>,
}

impl Entity {
    /// A well-formed entity: carried hash == hash of content.
    pub fn new(ty: &str, data: Value) -> Entity {
        let h = content_hash_bytes(ty, &data);
        Entity {
            ty: ty.to_string(),
            data,
            carried_hash: h,
        }
    }

    /// The true hash of what this entity currently carries as content.
    pub fn true_hash(&self) -> Vec<u8> {
        content_hash_bytes(&self.ty, &self.data)
    }

    /// Break the self-consistency of {type,data} <-> content_hash by one bit, leaving everything
    /// else — framing, canonicality, type, structure — untouched.
    ///
    /// One bit rather than a random hash on purpose: the refusal must be attributable to the
    /// hash comparison and to nothing else. A structurally odd hash could plausibly be refused by
    /// a length check or a format-code check, and those are different rows.
    pub fn with_corrupted_hash(mut self) -> Entity {
        let last = self.carried_hash.len() - 1;
        self.carried_hash[last] ^= 0x01;
        self
    }

    /// Mutate the content while leaving the carried hash pointing at the ORIGINAL content.
    /// Used by ECP-R7, whose defect is self-inconsistency of an `included` entry.
    pub fn with_mutated_data(mut self, data: Value) -> Entity {
        self.data = data;
        self
    }

    pub fn to_value(&self) -> Value {
        Value::Map(vec![
            (Value::text("type"), Value::text(&self.ty)),
            (Value::text("data"), self.data.clone()),
            (
                Value::text("content_hash"),
                Value::Bytes(self.carried_hash.clone()),
            ),
        ])
    }
}

/// §3.1 `system/protocol/envelope` on the wire (§5.3): {"root": entity, "included"?: map}.
pub struct Envelope {
    pub root: Entity,
    /// (key, entity). The key is a `system/hash` byte string (§3.1: "Map keys are CBOR byte
    /// strings (bstr), not text strings"). Carried as an explicit key so a probe can author a
    /// mis-keyed entry.
    pub included: Vec<(Vec<u8>, Entity)>,
}

impl Envelope {
    pub fn new(root: Entity) -> Envelope {
        Envelope {
            root,
            included: Vec::new(),
        }
    }

    pub fn with_included(mut self, key: Vec<u8>, e: Entity) -> Envelope {
        self.included.push((key, e));
        self
    }

    pub fn to_value(&self) -> Value {
        let mut entries = vec![(Value::text("root"), self.root.to_value())];
        if !self.included.is_empty() {
            let inc = Value::Map(
                self.included
                    .iter()
                    .map(|(k, e)| (Value::Bytes(k.clone()), e.to_value()))
                    .collect(),
            );
            entries.push((Value::text("included"), inc));
        }
        Value::Map(entries)
    }

    /// §5.1 frame structure: 4-byte big-endian length prefix, then the CBOR payload.
    pub fn to_frame(&self) -> Vec<u8> {
        let payload = encode(&self.to_value());
        let mut frame = Vec::with_capacity(4 + payload.len());
        frame.extend_from_slice(&(payload.len() as u32).to_be_bytes());
        frame.extend_from_slice(&payload);
        frame
    }
}

// ---------------------------------------------------------------------------------------------
// The hello EXECUTE — the vehicle for ECP-R3 and ECP-R7, and the negative control for all three
// ---------------------------------------------------------------------------------------------

/// §3.8 `system/protocol/connect/hello`.
///
/// Required fields per §3.8 and the §4.5 table: peer_id, nonce, protocols, timestamp.
/// `protocols` is Required-with-no-default and MUST be non-empty (§4.5, 0.8.2.4) — an empty or
/// absent one is `400 invalid_request` and would confound every probe built on this vehicle.
/// `hash_formats` and `key_types` are omitted deliberately: §4.5 gives them defaults
/// (["ecfv1-sha256"], ["ed25519"]) and the defaults are what we want, so stating them would be
/// a posture choice made silently.
pub fn hello_entity(peer_id: &str, nonce: &[u8], timestamp_ms: u64) -> Entity {
    Entity::new(
        "system/protocol/connect/hello",
        Value::Map(vec![
            (Value::text("peer_id"), Value::text(peer_id)),
            (Value::text("nonce"), Value::Bytes(nonce.to_vec())),
            (
                Value::text("protocols"),
                // §8.4's identifier. §4.5, 0.8.2.4: this vocabulary is the protocol VERSION id,
                // not a section number.
                Value::Array(vec![Value::text("entity-core/1.0")]),
            ),
            (Value::text("timestamp"), Value::U64(timestamp_ms)),
        ]),
    )
}

/// §3.2 `system/protocol/execute` targeting the pre-authorized connection path.
///
/// §3.2 / §4.2: "All EXECUTE requests MUST include `author` and `capability` — except requests
/// targeting the connection path (§4)." That exception is why this suite needs no Ed25519 to
/// reach any of its three requirements, and why every probe below is attributable to the defect
/// it injects rather than to a grant, an identity or a signature.
///
/// §4.3: URIs during connection setup are peer-relative.
pub fn hello_execute(request_id: &str, hello: Entity) -> Entity {
    Entity::new(
        "system/protocol/execute",
        Value::Map(vec![
            (Value::text("request_id"), Value::text(request_id)),
            (Value::text("uri"), Value::text("system/protocol/connect")),
            (Value::text("operation"), Value::text("hello")),
            (Value::text("params"), hello.to_value()),
        ]),
    )
}

/// A well-formed entity whose type is neither EXECUTE nor EXECUTE_RESPONSE — ECP-R57's subject.
///
/// §3.3's row is about a MESSAGE OF THE WRONG TYPE, not about bytes that fail to decode: the
/// framing arm is a different §4.11 row with the same code and a different cause, and a probe
/// that conflated them could not attribute its result. So this is canonical CBOR, correctly
/// framed, correctly self-hashed, carrying no CBOR tag — the ONLY thing wrong with it is the
/// root's type.
///
/// `primitive/any` with an empty-map data is chosen because §3.2's empty-params shape makes `a0`
/// an explicitly blessed canonical payload, so the entity cannot be refused for its content.
pub fn wrong_root_entity() -> Entity {
    Entity::new("primitive/any", Value::Map(vec![]))
}

/// An entity the hello has no use for — ECP-R7's unreferenced `included` subject.
pub fn bystander_entity(marker: u64) -> Entity {
    Entity::new(
        "primitive/any",
        Value::Map(vec![(Value::text("m"), Value::U64(marker))]),
    )
}
