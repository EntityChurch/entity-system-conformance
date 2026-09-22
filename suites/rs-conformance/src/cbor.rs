//! CBOR, encoder and decoder, from RFC 8949 and ENTITY-CBOR-ENCODING §4.1.
//!
//! Written here rather than taken from a crate: see Cargo.toml. Two suites exist precisely so
//! that they do not share a codec bug.
//!
//! The ENCODER emits Entity Canonical Form only (ECF §4.1 rules 1,2,3,5,6). There is no
//! non-canonical emit path, because a probe that is accidentally non-canonical measures
//! ENTITY-CBOR-ENCODING §6.3 / §4.11's framing arm instead of the row it names, and the two are
//! indistinguishable in the verdict.
//!
//! The DECODER is deliberately PERMISSIVE and REPORTS rather than rejects: it is reading a
//! peer's answer, and a peer that answers non-canonically has told us something we want to
//! record, not something we want to turn into a parse error.

use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    U64(u64),
    I64(i64),
    Bytes(Vec<u8>),
    Text(String),
    Array(Vec<Value>),
    /// Kept as an ordered vector, not a map: duplicate and mis-ordered keys are observations
    /// about the peer, and a BTreeMap would silently repair both.
    Map(Vec<(Value, Value)>),
    Bool(bool),
    Null,
    Undefined,
    F64(f64),
    Tag(u64, Box<Value>),
    Simple(u8),
}

impl Value {
    pub fn text(s: &str) -> Value {
        Value::Text(s.to_string())
    }

    /// Map lookup by text key. Returns the FIRST match; a duplicate key is a peer defect and is
    /// surfaced by `duplicate_keys()`, not papered over here.
    pub fn get(&self, key: &str) -> Option<&Value> {
        if let Value::Map(entries) = self {
            for (k, v) in entries {
                if let Value::Text(t) = k {
                    if t == key {
                        return Some(v);
                    }
                }
            }
        }
        None
    }

    pub fn as_u64(&self) -> Option<u64> {
        match self {
            Value::U64(n) => Some(*n),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Text(s) => Some(s.as_str()),
            _ => None,
        }
    }

    /// True if a CBOR tag (major type 6) appears anywhere in this value. ENTITY-CBOR-ENCODING
    /// §6.3 forbids them on data fields; we never emit one, and we record if a peer does.
    pub fn contains_tag(&self) -> bool {
        match self {
            Value::Tag(_, _) => true,
            Value::Array(items) => items.iter().any(|v| v.contains_tag()),
            Value::Map(entries) => entries
                .iter()
                .any(|(k, v)| k.contains_tag() || v.contains_tag()),
            _ => false,
        }
    }
}

// ---------------------------------------------------------------------------------------------
// Encoder — canonical only
// ---------------------------------------------------------------------------------------------

fn head(out: &mut Vec<u8>, major: u8, arg: u64) {
    // ECF §4.1 rule 1: minimal integer encoding. Never a longer form than the value needs.
    let mt = major << 5;
    if arg < 24 {
        out.push(mt | arg as u8);
    } else if arg <= u8::MAX as u64 {
        out.push(mt | 24);
        out.push(arg as u8);
    } else if arg <= u16::MAX as u64 {
        out.push(mt | 25);
        out.extend_from_slice(&(arg as u16).to_be_bytes());
    } else if arg <= u32::MAX as u64 {
        out.push(mt | 26);
        out.extend_from_slice(&(arg as u32).to_be_bytes());
    } else {
        out.push(mt | 27);
        out.extend_from_slice(&arg.to_be_bytes());
    }
}

/// Encode to Entity Canonical Form.
///
/// ECF §4.1 rule 2 is the one that is easy to get wrong and is the reason this is not a
/// straight RFC 8949 §4.2.1 sort: keys sort by ENCODED LENGTH FIRST, then lexicographically by
/// encoded bytes. That is RFC 8949's "length-first" (§4.2.3) ordering, not the bytewise one.
pub fn encode(v: &Value) -> Vec<u8> {
    let mut out = Vec::new();
    enc(v, &mut out);
    out
}

fn enc(v: &Value, out: &mut Vec<u8>) {
    match v {
        Value::U64(n) => head(out, 0, *n),
        Value::I64(n) => {
            if *n < 0 {
                head(out, 1, (-1 - *n) as u64);
            } else {
                head(out, 0, *n as u64);
            }
        }
        Value::Bytes(b) => {
            head(out, 2, b.len() as u64);
            out.extend_from_slice(b);
        }
        Value::Text(s) => {
            head(out, 3, s.len() as u64);
            out.extend_from_slice(s.as_bytes());
        }
        Value::Array(items) => {
            // rule 3: definite length only.
            head(out, 4, items.len() as u64);
            for i in items {
                enc(i, out);
            }
        }
        Value::Map(entries) => {
            // rule 2 + rule 5. Encode every key, sort by (len, bytes), reject duplicates by
            // construction (a BTreeMap on the encoded key bytes collapses them, and a collapse
            // here would hide a bug in a probe builder).
            let mut sorted: BTreeMap<(usize, Vec<u8>), Vec<u8>> = BTreeMap::new();
            for (k, val) in entries {
                let kb = encode(k);
                let vb = encode(val);
                let prev = sorted.insert((kb.len(), kb), vb);
                debug_assert!(prev.is_none(), "duplicate map key in a probe we authored");
            }
            head(out, 5, sorted.len() as u64);
            for ((_, kb), vb) in sorted {
                out.extend_from_slice(&kb);
                out.extend_from_slice(&vb);
            }
        }
        Value::Bool(b) => out.push(0xe0 | if *b { 21 } else { 20 }),
        Value::Null => out.push(0xf6),
        Value::Undefined => out.push(0xf7),
        Value::Simple(n) => {
            if *n < 24 {
                out.push(0xe0 | n)
            } else {
                out.push(0xf8);
                out.push(*n)
            }
        }
        Value::F64(f) => {
            // ECF §4.1 rule 4/4a: shortest float that preserves the value.
            // We never author a float in these probes; implemented for completeness and
            // exercised by selftest so it is not dead code pretending to work.
            out.extend_from_slice(&shortest_float(*f));
        }
        Value::Tag(t, inner) => {
            // We never EMIT a tag in a protocol frame (§6.3). Present so a decoded value can be
            // re-encoded for display.
            head(out, 6, *t);
            enc(inner, out);
        }
    }
}

fn shortest_float(f: f64) -> Vec<u8> {
    // Rule 4a: the four special values have pinned bytes.
    if f.is_nan() {
        return vec![0xf9, 0x7e, 0x00];
    }
    if f == f64::INFINITY {
        return vec![0xf9, 0x7c, 0x00];
    }
    if f == f64::NEG_INFINITY {
        return vec![0xf9, 0xfc, 0x00];
    }
    if f == 0.0 && f.is_sign_negative() {
        return vec![0xf9, 0x80, 0x00];
    }
    let f32v = f as f32;
    if f32v as f64 == f {
        if let Some(h) = f32_to_f16(f32v) {
            let mut v = vec![0xf9];
            v.extend_from_slice(&h.to_be_bytes());
            return v;
        }
        let mut v = vec![0xfa];
        v.extend_from_slice(&f32v.to_be_bytes());
        return v;
    }
    let mut v = vec![0xfb];
    v.extend_from_slice(&f.to_be_bytes());
    v
}

fn f32_to_f16(f: f32) -> Option<u16> {
    let bits = f.to_bits();
    let sign = ((bits >> 16) & 0x8000) as u16;
    let exp = ((bits >> 23) & 0xff) as i32;
    let mant = bits & 0x7f_ffff;
    if exp == 0 && mant == 0 {
        return Some(sign);
    }
    let unbiased = exp - 127;
    if (-14..=15).contains(&unbiased) && (mant & 0x1fff) == 0 {
        Some(sign | (((unbiased + 15) as u16) << 10) | ((mant >> 13) as u16))
    } else {
        None
    }
}

// ---------------------------------------------------------------------------------------------
// Decoder — permissive, reports what it saw
// ---------------------------------------------------------------------------------------------

pub struct Decoder<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> Decoder<'a> {
    pub fn new(buf: &'a [u8]) -> Self {
        Decoder { buf, pos: 0 }
    }

    pub fn decode(&mut self) -> Result<Value, String> {
        self.item(0)
    }

    fn byte(&mut self) -> Result<u8, String> {
        let b = *self
            .buf
            .get(self.pos)
            .ok_or_else(|| format!("truncated at {}", self.pos))?;
        self.pos += 1;
        Ok(b)
    }

    fn take(&mut self, n: usize) -> Result<&'a [u8], String> {
        if self.pos + n > self.buf.len() {
            return Err(format!(
                "truncated: want {} bytes at {}, have {}",
                n,
                self.pos,
                self.buf.len() - self.pos
            ));
        }
        let s = &self.buf[self.pos..self.pos + n];
        self.pos += n;
        Ok(s)
    }

    fn arg(&mut self, ai: u8) -> Result<Option<u64>, String> {
        Ok(match ai {
            0..=23 => Some(ai as u64),
            24 => Some(self.byte()? as u64),
            25 => {
                let b = self.take(2)?;
                Some(u16::from_be_bytes([b[0], b[1]]) as u64)
            }
            26 => {
                let b = self.take(4)?;
                Some(u32::from_be_bytes([b[0], b[1], b[2], b[3]]) as u64)
            }
            27 => {
                let b = self.take(8)?;
                Some(u64::from_be_bytes([
                    b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
                ]))
            }
            31 => None, // indefinite length
            _ => return Err(format!("reserved additional info {}", ai)),
        })
    }

    fn item(&mut self, depth: u32) -> Result<Value, String> {
        if depth > 64 {
            return Err("nesting deeper than 64".into());
        }
        let ib = self.byte()?;
        let major = ib >> 5;
        let ai = ib & 0x1f;

        match major {
            0 => Ok(Value::U64(
                self.arg(ai)?.ok_or("indefinite length on a uint")?,
            )),
            1 => {
                let n = self.arg(ai)?.ok_or("indefinite length on a nint")?;
                Ok(Value::I64(-1i64 - n as i64))
            }
            2 | 3 => {
                match self.arg(ai)? {
                    Some(n) => {
                        let b = self.take(n as usize)?.to_vec();
                        if major == 2 {
                            Ok(Value::Bytes(b))
                        } else {
                            Ok(Value::Text(String::from_utf8_lossy(&b).into_owned()))
                        }
                    }
                    None => {
                        // indefinite-length string: concatenate chunks until break.
                        let mut acc = Vec::new();
                        loop {
                            if *self.buf.get(self.pos).ok_or("truncated in chunks")? == 0xff {
                                self.pos += 1;
                                break;
                            }
                            match self.item(depth + 1)? {
                                Value::Bytes(b) => acc.extend_from_slice(&b),
                                Value::Text(t) => acc.extend_from_slice(t.as_bytes()),
                                _ => return Err("non-string chunk in indefinite string".into()),
                            }
                        }
                        if major == 2 {
                            Ok(Value::Bytes(acc))
                        } else {
                            Ok(Value::Text(String::from_utf8_lossy(&acc).into_owned()))
                        }
                    }
                }
            }
            4 => {
                let mut items = Vec::new();
                match self.arg(ai)? {
                    Some(n) => {
                        for _ in 0..n {
                            items.push(self.item(depth + 1)?);
                        }
                    }
                    None => loop {
                        if *self.buf.get(self.pos).ok_or("truncated in array")? == 0xff {
                            self.pos += 1;
                            break;
                        }
                        items.push(self.item(depth + 1)?);
                    },
                }
                Ok(Value::Array(items))
            }
            5 => {
                let mut entries = Vec::new();
                match self.arg(ai)? {
                    Some(n) => {
                        for _ in 0..n {
                            let k = self.item(depth + 1)?;
                            let v = self.item(depth + 1)?;
                            entries.push((k, v));
                        }
                    }
                    None => loop {
                        if *self.buf.get(self.pos).ok_or("truncated in map")? == 0xff {
                            self.pos += 1;
                            break;
                        }
                        let k = self.item(depth + 1)?;
                        let v = self.item(depth + 1)?;
                        entries.push((k, v));
                    },
                }
                Ok(Value::Map(entries))
            }
            6 => {
                let t = self.arg(ai)?.ok_or("indefinite length on a tag")?;
                let inner = self.item(depth + 1)?;
                Ok(Value::Tag(t, Box::new(inner)))
            }
            7 => match ai {
                20 => Ok(Value::Bool(false)),
                21 => Ok(Value::Bool(true)),
                22 => Ok(Value::Null),
                23 => Ok(Value::Undefined),
                24 => Ok(Value::Simple(self.byte()?)),
                25 => {
                    let b = self.take(2)?;
                    Ok(Value::F64(f16_to_f64(u16::from_be_bytes([b[0], b[1]]))))
                }
                26 => {
                    let b = self.take(4)?;
                    Ok(Value::F64(
                        f32::from_be_bytes([b[0], b[1], b[2], b[3]]) as f64
                    ))
                }
                27 => {
                    let b = self.take(8)?;
                    Ok(Value::F64(f64::from_be_bytes([
                        b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7],
                    ])))
                }
                _ => Ok(Value::Simple(ai)),
            },
            _ => Err(format!("impossible major type {}", major)),
        }
    }
}

fn f16_to_f64(h: u16) -> f64 {
    let sign = if h & 0x8000 != 0 { -1.0 } else { 1.0 };
    let exp = ((h >> 10) & 0x1f) as i32;
    let mant = (h & 0x3ff) as f64;
    if exp == 0 {
        sign * mant * 2f64.powi(-24)
    } else if exp == 31 {
        if mant == 0.0 {
            sign * f64::INFINITY
        } else {
            f64::NAN
        }
    } else {
        sign * (mant + 1024.0) * 2f64.powi(exp - 25)
    }
}

/// Encoder self-test against ENTITY-CBOR-ENCODING §4.1's own worked examples and Appendix A.
/// Runs on every invocation for the same reason `sha256::selftest` does.
pub fn selftest() -> Result<(), String> {
    let check = |v: Value, want: &str, label: &str| -> Result<(), String> {
        let got = crate::sha256::hex(&encode(&v));
        if got != want {
            return Err(format!("cbor selftest FAILED [{}]: got {} want {}", label, got, want));
        }
        Ok(())
    };

    // §4.1 rule 1 — minimal integer encoding.
    check(Value::U64(1), "01", "uint 1")?;
    check(Value::U64(23), "17", "uint 23")?;
    check(Value::U64(24), "1818", "uint 24")?;
    check(Value::U64(1_000_000), "1a000f4240", "uint 1e6")?;

    // §4.1 rule 2 — the worked example in the spec text itself:
    //   {"bb": 1, "a": 2, "ccc": 3}  ->  A3 6161 02 626262 01 63636363 03
    // Note this is LENGTH-FIRST ordering, not plain bytewise.
    check(
        Value::Map(vec![
            (Value::text("bb"), Value::U64(1)),
            (Value::text("a"), Value::U64(2)),
            (Value::text("ccc"), Value::U64(3)),
        ]),
        "a3616102626262016363636303",
        "ECF §4.1 rule 2 worked example",
    )?;

    // §4.1 rule 3 — definite lengths.
    check(
        Value::Array(vec![Value::U64(1), Value::U64(2), Value::U64(3)]),
        "83010203",
        "array(3)",
    )?;

    // §4.1 rule 4 / 4a — the pinned special values.
    check(Value::F64(1.0), "f93c00", "float 1.0")?;
    check(Value::F64(f64::NAN), "f97e00", "NaN")?;
    check(Value::F64(-0.0), "f98000", "-0.0")?;
    check(Value::F64(f64::INFINITY), "f97c00", "+Inf")?;
    check(Value::F64(f64::NEG_INFINITY), "f9fc00", "-Inf")?;

    // §3.2 of ENTITY-CORE-PROTOCOL: the empty-params shape is the single byte a0.
    check(Value::Map(vec![]), "a0", "empty map")?;

    // Round-trip: decode what we encode.
    let v = Value::Map(vec![
        (Value::text("data"), Value::Map(vec![])),
        (Value::text("type"), Value::text("primitive/any")),
    ]);
    let bytes = encode(&v);
    let back = Decoder::new(&bytes).decode().map_err(|e| format!("cbor selftest round-trip decode failed: {}", e))?;
    if back != v {
        return Err("cbor selftest FAILED: round-trip mismatch".into());
    }

    Ok(())
}
