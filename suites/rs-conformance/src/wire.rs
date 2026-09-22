//! Transport and, more importantly, OUTCOME CLASSIFICATION.
//!
//! §4.11 (0.8.2.25) names two non-conformant behaviours and says in terms that they are
//! "distinct failures rather than one":
//!
//!   * dropping the frame  — no response and no close
//!   * closing with no coded frame
//!
//! "SCORED SEPARATELY. Collapsing them lets a peer get credit for the wrong fix." So the
//! observation type below has a distinct variant for each, and nothing in this suite is allowed
//! to map them onto one verdict string. This is the single most load-bearing file in the suite:
//! a classifier that cannot tell a bare close from a silent drop produces a top-line verdict
//! that looks entirely correct and answers the wrong question.

use crate::cbor::{Decoder, Value};
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::time::Duration;

/// What a peer did with one frame. Every variant is a DIFFERENT observation, never a severity.
#[derive(Debug, Clone)]
pub enum Outcome {
    /// A frame came back and decoded.
    Frame(Frame),
    /// A frame came back and did not decode as CBOR, or did not decode as an envelope.
    /// Distinct from every other variant: the peer answered, and the answer is unreadable.
    Unreadable { bytes: usize, why: String },
    /// The socket closed with no frame at all on it. §4.11's SECOND named failure.
    BareClose,
    /// No frame, no close, within the deadline. §4.11's FIRST named failure.
    SilentDrop,
    /// We never got as far as sending. Not a verdict about the peer.
    Unreachable(String),
}

#[derive(Debug, Clone)]
pub struct Frame {
    pub root_type: String,
    pub request_id: Option<String>,
    pub status: Option<u64>,
    pub code: Option<String>,
    pub message: Option<String>,
    /// Whether the peer closed the connection after answering. §4.11: "Whether the peer closes
    /// the connection afterwards is its own choice." Recorded, NEVER scored.
    pub closed_after: bool,
    /// ENTITY-CBOR-ENCODING §6.3 forbids CBOR tags on data fields. If a peer's own answer
    /// carries one that is an observation about the peer, recorded here.
    pub answer_carried_tag: bool,
    pub correlated: bool,
}

pub struct Conn {
    stream: TcpStream,
    pub read_timeout: Duration,
}

impl Conn {
    /// One connection per probe, deliberately.
    ///
    /// §4.11 (0.8.2.26) lets a peer "bound the number of consecutive pre-admission refusals it
    /// answers on one connection before closing, as local policy [MAY]" and says a check set
    /// "MUST NOT assert a particular limit and MUST NOT assert its absence". Reusing one
    /// connection across probes would make our later probes measure that local policy instead of
    /// the row they name — and a peer that had legitimately hit its bound would be scored as a
    /// silent drop. A fresh connection makes every probe the FIRST refusal on its connection.
    pub fn open(addr: &str, connect_timeout: Duration, read_timeout: Duration) -> Result<Conn, String> {
        let sockaddr = addr
            .to_socket_addrs()
            .map_err(|e| format!("cannot resolve {}: {}", addr, e))?
            .next()
            .ok_or_else(|| format!("no address for {}", addr))?;
        let stream = TcpStream::connect_timeout(&sockaddr, connect_timeout)
            .map_err(|e| format!("connect {}: {}", addr, e))?;
        stream
            .set_read_timeout(Some(read_timeout))
            .map_err(|e| format!("set_read_timeout: {}", e))?;
        stream
            .set_write_timeout(Some(connect_timeout))
            .map_err(|e| format!("set_write_timeout: {}", e))?;
        stream.set_nodelay(true).ok();
        Ok(Conn {
            stream,
            read_timeout,
        })
    }

    pub fn send_frame(&mut self, frame: &[u8]) -> Result<(), String> {
        self.stream
            .write_all(frame)
            .map_err(|e| format!("write: {}", e))?;
        self.stream.flush().map_err(|e| format!("flush: {}", e))
    }

    /// Read exactly `n` bytes, distinguishing the three terminations that matter.
    fn read_exact_classified(&mut self, n: usize) -> ReadResult {
        let mut buf = vec![0u8; n];
        let mut got = 0;
        while got < n {
            match self.stream.read(&mut buf[got..]) {
                Ok(0) => {
                    return if got == 0 {
                        ReadResult::Eof
                    } else {
                        ReadResult::PartialThenEof(got)
                    }
                }
                Ok(k) => got += k,
                Err(e) => {
                    return match e.kind() {
                        std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut => {
                            if got == 0 {
                                ReadResult::Timeout
                            } else {
                                ReadResult::PartialThenTimeout(got)
                            }
                        }
                        _ => ReadResult::Err(format!("{}", e)),
                    }
                }
            }
        }
        ReadResult::Ok(buf)
    }

    /// Send one frame and classify the single answer, if any.
    pub fn exchange(&mut self, frame: &[u8]) -> Outcome {
        if let Err(e) = self.send_frame(frame) {
            // A write failure on a connection we just opened is the peer closing on us before
            // it read anything. That is still a bare close from the caller's point of view, but
            // we do not silently call it one — it is reported as what it was.
            return Outcome::Unreachable(format!("send failed: {}", e));
        }

        // §5.1: 4-byte big-endian length prefix.
        let len = match self.read_exact_classified(4) {
            ReadResult::Ok(b) => u32::from_be_bytes([b[0], b[1], b[2], b[3]]) as usize,
            ReadResult::Eof => return Outcome::BareClose,
            ReadResult::Timeout => return Outcome::SilentDrop,
            ReadResult::PartialThenEof(k) => {
                return Outcome::Unreadable {
                    bytes: k,
                    why: format!("{} of 4 length-prefix bytes, then EOF", k),
                }
            }
            ReadResult::PartialThenTimeout(k) => {
                return Outcome::Unreadable {
                    bytes: k,
                    why: format!("{} of 4 length-prefix bytes, then timeout", k),
                }
            }
            ReadResult::Err(e) => return Outcome::Unreachable(format!("read: {}", e)),
        };

        // §5.1: "Maximum message size SHOULD be 16 MiB". We refuse to allocate beyond it rather
        // than let a peer's length prefix size our heap.
        if len > 16 * 1024 * 1024 {
            return Outcome::Unreadable {
                bytes: 4,
                why: format!("length prefix {} exceeds the §5.1 16 MiB maximum", len),
            };
        }

        let payload = match self.read_exact_classified(len) {
            ReadResult::Ok(b) => b,
            ReadResult::Eof => {
                return Outcome::Unreadable {
                    bytes: 4,
                    why: format!("length prefix said {} bytes, then EOF with none of them", len),
                }
            }
            ReadResult::Timeout => {
                return Outcome::Unreadable {
                    bytes: 4,
                    why: format!("length prefix said {} bytes, none arrived before the deadline", len),
                }
            }
            ReadResult::PartialThenEof(k) | ReadResult::PartialThenTimeout(k) => {
                return Outcome::Unreadable {
                    bytes: 4 + k,
                    why: format!("truncated body: {} of {} bytes", k, len),
                }
            }
            ReadResult::Err(e) => return Outcome::Unreachable(format!("read body: {}", e)),
        };

        let value = match Decoder::new(&payload).decode() {
            Ok(v) => v,
            Err(e) => {
                return Outcome::Unreadable {
                    bytes: payload.len(),
                    why: format!("payload is not decodable CBOR: {}", e),
                }
            }
        };

        let mut frame = match parse_envelope(&value) {
            Ok(f) => f,
            Err(e) => {
                return Outcome::Unreadable {
                    bytes: payload.len(),
                    why: e,
                }
            }
        };

        frame.answer_carried_tag = value.contains_tag();
        frame.closed_after = self.observe_close();
        Outcome::Frame(frame)
    }

    /// After an answer, look briefly for an EOF. Purely an observation: §4.11 makes the close the
    /// peer's own choice and neither shape is preferred, so this NEVER feeds a verdict.
    fn observe_close(&mut self) -> bool {
        let grace = Duration::from_millis(400).min(self.read_timeout);
        let _ = self.stream.set_read_timeout(Some(grace));
        let mut b = [0u8; 1];
        let closed = matches!(self.stream.read(&mut b), Ok(0));
        let _ = self.stream.set_read_timeout(Some(self.read_timeout));
        closed
    }
}

enum ReadResult {
    Ok(Vec<u8>),
    Eof,
    Timeout,
    PartialThenEof(usize),
    PartialThenTimeout(usize),
    Err(String),
}

/// Pull the fields a verdict needs out of a received envelope (§3.1, §3.3).
fn parse_envelope(v: &Value) -> Result<Frame, String> {
    let root = v
        .get("root")
        .ok_or_else(|| "decoded CBOR has no `root` key — not an envelope (§3.1)".to_string())?;
    let root_type = root
        .get("type")
        .and_then(|t| t.as_str())
        .ok_or_else(|| "envelope `root` has no text `type` (§5.3)".to_string())?
        .to_string();
    let data = root.get("data");

    let request_id = data
        .and_then(|d| d.get("request_id"))
        .and_then(|r| r.as_str())
        .map(|s| s.to_string());

    // §3.3: status is the numeric category on EXECUTE_RESPONSE.
    let status = data.and_then(|d| d.get("status")).and_then(|s| s.as_u64());

    // §3.3: `result.data.code` carries the specific error within that category.
    let result = data.and_then(|d| d.get("result"));
    let code = result
        .and_then(|r| r.get("data"))
        .and_then(|d| d.get("code"))
        .and_then(|c| c.as_str())
        .map(|s| s.to_string());
    let message = result
        .and_then(|r| r.get("data"))
        .and_then(|d| d.get("message"))
        .and_then(|m| m.as_str())
        .map(|s| s.to_string());

    Ok(Frame {
        root_type,
        request_id,
        status,
        code,
        message,
        closed_after: false,
        answer_carried_tag: false,
        correlated: false,
    })
}
