//! RFC 8785 JSON Canonicalization of a checked document, and the lockfile integrity
//! (SPEC §6.2). Same as `jcs.ts`/`jcs.py`; `fixtures/jcs/corpus.json` pins the bytes in all
//! three ports. SHA-256 (FIPS 180-4) and base64 (RFC 4648 §4) are written here so the crate
//! keeps its single dependency; the corpus and NIST vectors test them.
//!
//! Implements: C-098

use std::fmt::Write as _;
use std::num::FpCategory;

use crate::Problem;
use crate::schema::int_to_f64;
use crate::value::Value;

/// ECMAScript `Number::toString` of a double (RFC 8785 §3.2.2.3).
fn number(x: f64, out: &mut String) -> Result<(), Problem> {
    if !x.is_finite() {
        return Err(Problem::NonFinite);
    }
    finite(x, out);
    Ok(())
}

/// The ECMAScript form of a finite double (RFC 8785 §3.2.2.3).
fn finite(x: f64, out: &mut String) {
    if x.classify() == FpCategory::Zero {
        out.push('0');
        return;
    }
    if x.is_sign_negative() {
        out.push('-');
    }
    // `{:e}` prints the shortest round-tripping digits: `1.2345e2`, `5e-7`.
    let sci = format!("{:e}", x.abs());
    let (mantissa, exponent) = sci.split_once('e').unwrap_or_default();
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let k = i64::try_from(digits.len()).unwrap_or_default();
    // The decimal point sits after `n` digits.
    let n = exponent.parse::<i64>().unwrap_or_default().saturating_add(1);
    let zeros = |count: i64| "0".repeat(usize::try_from(count).unwrap_or_default());
    if k <= n && n <= 21 {
        out.push_str(&digits);
        out.push_str(&zeros(n.saturating_sub(k)));
    } else if 0 < n && n <= 21 {
        let (whole, fraction) =
            digits.split_at_checked(usize::try_from(n).unwrap_or_default()).unwrap_or_default();
        out.push_str(whole);
        out.push('.');
        out.push_str(fraction);
    } else if -6 < n && n <= 0 {
        out.push_str("0.");
        out.push_str(&zeros(n.saturating_neg()));
        out.push_str(&digits);
    } else {
        let (first, rest) = digits.split_at_checked(1).unwrap_or_default();
        out.push_str(first);
        if !rest.is_empty() {
            out.push('.');
            out.push_str(rest);
        }
        let e = n.saturating_sub(1);
        out.push('e');
        out.push(if e >= 0 { '+' } else { '-' });
        out.push_str(&e.unsigned_abs().to_string());
    }
}

/// A JSON string as `JSON.stringify` writes it.
fn string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c < ' ' => {
                let _ = write!(out, "\\u{:04x}", u32::from(c));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn members(entries: &mut [(&str, &Value)], out: &mut String) -> Result<(), Problem> {
    // RFC 8785 §3.2.3: keys sorted by UTF-16 code units; keys are distinct.
    entries.sort_by(|(a, _), (b, _)| a.encode_utf16().cmp(b.encode_utf16()));
    out.push('{');
    for (i, (key, value)) in entries.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        string(key, out);
        out.push(':');
        canonical(value, out)?;
    }
    out.push('}');
    Ok(())
}

/// Append the canonical JSON of `value` to `out`.
pub(crate) fn canonical(value: &Value, out: &mut String) -> Result<(), Problem> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        // Integers become doubles, as I-JSON requires (RFC 8785 §3.2.2.3; SPEC §13 item 5 is open).
        Value::Int(n) => finite(int_to_f64(*n), out),
        Value::Float(f) => number(*f, out)?,
        Value::String(s) => string(s, out),
        Value::Sequence(items) => {
            out.push('[');
            for (i, item) in items.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                canonical(item, out)?;
            }
            out.push(']');
        }
        Value::Mapping(_) => members(&mut value.entries(), out)?,
    }
    Ok(())
}

/// `sha256-<base64>` of the canonical form of `root` without its top-level `integrity` key.
pub(crate) fn integrity_of(root: &Value) -> Result<String, Problem> {
    let mut entries: Vec<(&str, &Value)> =
        root.entries().into_iter().filter(|(k, _)| *k != "integrity").collect();
    let mut body = String::new();
    members(&mut entries, &mut body)?;
    Ok(format!("sha256-{}", base64_32(sha256(body.as_bytes()))))
}

const K: [u32; 64] = [
    0x428a_2f98,
    0x7137_4491,
    0xb5c0_fbcf,
    0xe9b5_dba5,
    0x3956_c25b,
    0x59f1_11f1,
    0x923f_82a4,
    0xab1c_5ed5,
    0xd807_aa98,
    0x1283_5b01,
    0x2431_85be,
    0x550c_7dc3,
    0x72be_5d74,
    0x80de_b1fe,
    0x9bdc_06a7,
    0xc19b_f174,
    0xe49b_69c1,
    0xefbe_4786,
    0x0fc1_9dc6,
    0x240c_a1cc,
    0x2de9_2c6f,
    0x4a74_84aa,
    0x5cb0_a9dc,
    0x76f9_88da,
    0x983e_5152,
    0xa831_c66d,
    0xb003_27c8,
    0xbf59_7fc7,
    0xc6e0_0bf3,
    0xd5a7_9147,
    0x06ca_6351,
    0x1429_2967,
    0x27b7_0a85,
    0x2e1b_2138,
    0x4d2c_6dfc,
    0x5338_0d13,
    0x650a_7354,
    0x766a_0abb,
    0x81c2_c92e,
    0x9272_2c85,
    0xa2bf_e8a1,
    0xa81a_664b,
    0xc24b_8b70,
    0xc76c_51a3,
    0xd192_e819,
    0xd699_0624,
    0xf40e_3585,
    0x106a_a070,
    0x19a4_c116,
    0x1e37_6c08,
    0x2748_774c,
    0x34b0_bcb5,
    0x391c_0cb3,
    0x4ed8_aa4a,
    0x5b9c_ca4f,
    0x682e_6ff3,
    0x748f_82ee,
    0x78a5_636f,
    0x84c8_7814,
    0x8cc7_0208,
    0x90be_fffa,
    0xa450_6ceb,
    0xbef9_a3f7,
    0xc671_78f2,
];

const H0: [u32; 8] =
    [0x6a09_e667, 0xbb67_ae85, 0x3c6e_f372, 0xa54f_f53a, 0x510e_527f, 0x9b05_688c, 0x1f83_d9ab, 0x5be0_cd19];

#[expect(clippy::many_single_char_names, reason = "FIPS 180-4 names the working variables a..h")]
fn compress(state: &mut [u32; 8], block: &[u8]) {
    let mut w = [0_u32; 16];
    for (slot, word) in w.iter_mut().zip(block.chunks_exact(4)) {
        *slot = u32::from_be_bytes(word.try_into().unwrap_or_default());
    }
    let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut h] = *state;
    for k in K {
        // `w` holds W[t..t+16]; W[t+16] = σ1(W[t+14]) + W[t+9] + σ0(W[t+1]) + W[t].
        let [w0, w1, w2, w3, w4, w5, w6, w7, w8, w9, w10, w11, w12, w13, w14, w15] = w;
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let ch = (e & f) ^ (!e & g);
        let t1 = h.wrapping_add(s1).wrapping_add(ch).wrapping_add(k).wrapping_add(w0);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let maj = (a & b) ^ (a & c) ^ (b & c);
        let t2 = s0.wrapping_add(maj);
        (h, g, f, e, d, c, b, a) = (g, f, e, d.wrapping_add(t1), c, b, a, t1.wrapping_add(t2));
        let sigma0 = w1.rotate_right(7) ^ w1.rotate_right(18) ^ (w1 >> 3);
        let sigma1 = w14.rotate_right(17) ^ w14.rotate_right(19) ^ (w14 >> 10);
        let next = sigma1.wrapping_add(w9).wrapping_add(sigma0).wrapping_add(w0);
        w = [w1, w2, w3, w4, w5, w6, w7, w8, w9, w10, w11, w12, w13, w14, w15, next];
    }
    for (s, v) in state.iter_mut().zip([a, b, c, d, e, f, g, h]) {
        *s = s.wrapping_add(v);
    }
}

/// SHA-256 of `data` (FIPS 180-4).
pub(crate) fn sha256(data: &[u8]) -> [u8; 32] {
    let bits = u64::try_from(data.len()).unwrap_or_default().wrapping_mul(8);
    let mut message = data.to_vec();
    message.push(0x80);
    while message.len() % 64 != 56 {
        message.push(0);
    }
    message.extend_from_slice(&bits.to_be_bytes());
    let mut state = H0;
    for block in message.chunks_exact(64) {
        compress(&mut state, block);
    }
    let mut out = [0_u8; 32];
    for (chunk, word) in out.chunks_exact_mut(4).zip(state) {
        chunk.copy_from_slice(&word.to_be_bytes());
    }
    out
}

const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// Standard base64 of 32 bytes: 43 characters and one `=`.
fn base64_32(bytes: [u8; 32]) -> String {
    // A zero byte makes 33 bytes, 11 whole groups; its last character is then the padding.
    let mut padded = bytes.to_vec();
    padded.push(0);
    let mut out = String::with_capacity(44);
    for group in padded.chunks_exact(3) {
        let [x, y, z]: [u8; 3] = group.try_into().unwrap_or_default();
        let n = u32::from_be_bytes([0, x, y, z]);
        for shift in [18, 12, 6, 0] {
            let index = usize::try_from((n >> shift) & 63).unwrap_or_default();
            out.push(char::from(ALPHABET.get(index).copied().unwrap_or(b'=')));
        }
    }
    out.pop();
    out.push('=');
    out
}

#[cfg(test)]
#[expect(clippy::expect_used, clippy::indexing_slicing, reason = "tests: a bad fixture is a test failure")]
mod tests {
    use super::{base64_32, canonical, sha256};
    use crate::Problem;
    use crate::profile::parse_root;
    use crate::value::Value;

    /// `fixtures/jcs/corpus.json`: the same bytes as the JS and Python ports, and as rfc8785.
    #[test]
    fn golden_corpus() {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../fixtures/jcs/corpus.json");
        let doc: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(path).expect("fixture readable"))
                .expect("fixture JSON valid");
        let cases = doc["cases"].as_array().expect("array");
        assert!(cases.len() >= 30);
        for case in cases {
            let name = case["name"].as_str().expect("string");
            let root =
                parse_root(&format!("{}\n", case["yaml"].as_str().expect("string"))).expect("valid YAML");
            let mut out = String::new();
            let got = canonical(&Value::Mapping(root), &mut out).map(|()| out);
            if let Some(want) = case["jcs"].as_str() {
                assert_eq!(got.as_deref(), Ok(want), "{name}");
            } else {
                assert_eq!(got, Err(Problem::NonFinite), "{name}");
                assert_eq!(
                    Problem::NonFinite.to_string(),
                    "a number that is not finite has no canonical JSON form"
                );
            }
        }
    }

    fn hex(bytes: &[u8]) -> String {
        bytes
            .iter()
            .flat_map(|b| [b >> 4, b & 15])
            .map(|n| char::from_digit(n.into(), 16).unwrap_or('?'))
            .collect()
    }

    #[test]
    fn nist_vectors() {
        assert_eq!(hex(&sha256(b"")), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
        assert_eq!(hex(&sha256(b"abc")), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
        assert_eq!(
            hex(&sha256(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
        );
        assert_eq!(
            hex(&sha256(&vec![b'a'; 1_000_000])),
            "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"
        );
    }

    #[test]
    fn base64_of_a_digest() {
        assert_eq!(base64_32(sha256(b"")), "47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=");
    }
}
