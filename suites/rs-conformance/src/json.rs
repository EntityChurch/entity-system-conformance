//! A minimal JSON writer. The verdict document is a contract surface
//! (`docs/DESIGN-THE-SUITE-CONTRACT.md` §2), so it is built from an explicit tree rather than
//! from string concatenation — an unescaped peer-supplied `message` would otherwise be able to
//! corrupt a verdict document, and a corrupt verdict that still parses is exactly the failure
//! this seat exists to refuse.

pub enum J {
    S(String),
    N(u64),
    B(bool),
    Null,
    A(Vec<J>),
    O(Vec<(String, J)>),
}

impl J {
    pub fn s(v: &str) -> J {
        J::S(v.to_string())
    }
    pub fn opt_s(v: &Option<String>) -> J {
        match v {
            Some(x) => J::S(x.clone()),
            None => J::Null,
        }
    }
    pub fn opt_n(v: &Option<u64>) -> J {
        match v {
            Some(x) => J::N(*x),
            None => J::Null,
        }
    }
}

pub fn write(v: &J, indent: usize, out: &mut String) {
    let pad = "  ".repeat(indent);
    let pad1 = "  ".repeat(indent + 1);
    match v {
        J::S(s) => {
            out.push('"');
            escape(s, out);
            out.push('"');
        }
        J::N(n) => out.push_str(&n.to_string()),
        J::B(b) => out.push_str(if *b { "true" } else { "false" }),
        J::Null => out.push_str("null"),
        J::A(items) => {
            if items.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push_str("[\n");
            for (i, it) in items.iter().enumerate() {
                out.push_str(&pad1);
                write(it, indent + 1, out);
                if i + 1 < items.len() {
                    out.push(',');
                }
                out.push('\n');
            }
            out.push_str(&pad);
            out.push(']');
        }
        J::O(fields) => {
            if fields.is_empty() {
                out.push_str("{}");
                return;
            }
            out.push_str("{\n");
            for (i, (k, val)) in fields.iter().enumerate() {
                out.push_str(&pad1);
                out.push('"');
                escape(k, out);
                out.push_str("\": ");
                write(val, indent + 1, out);
                if i + 1 < fields.len() {
                    out.push(',');
                }
                out.push('\n');
            }
            out.push_str(&pad);
            out.push('}');
        }
    }
}

fn escape(s: &str, out: &mut String) {
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
}

pub fn to_string(v: &J) -> String {
    let mut s = String::new();
    write(v, 0, &mut s);
    s.push('\n');
    s
}

/// Base58 (Bitcoin alphabet), for the §1.5/§7.4 peer-id string form.
/// Needed because §3.8's hello carries `peer_id: system/peer-id`, and §5.4's `is_peer_id`
/// requires >= 46 Base58 characters — a peer that validates the field would otherwise refuse our
/// probe for a reason that is not the row under test.
pub fn base58(data: &[u8]) -> String {
    const ALPHABET: &[u8] = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
    let mut digits: Vec<u8> = vec![0];
    for &byte in data {
        let mut carry = byte as u32;
        for d in digits.iter_mut() {
            carry += (*d as u32) << 8;
            *d = (carry % 58) as u8;
            carry /= 58;
        }
        while carry > 0 {
            digits.push((carry % 58) as u8);
            carry /= 58;
        }
    }
    let mut out = String::new();
    for &b in data {
        if b == 0 {
            out.push('1');
        } else {
            break;
        }
    }
    for &d in digits.iter().rev() {
        out.push(ALPHABET[d as usize] as char);
    }
    // Strip the single artefact zero-digit the accumulator starts with, when the value is not 0.
    if out.len() > 1 && data.iter().any(|&b| b != 0) {
        if let Some(stripped) = out.strip_prefix('1') {
            if data[0] != 0 {
                return stripped.to_string();
            }
        }
    }
    out
}
