//! String formats of the urim 0.2 type vocabulary (SPEC §5.1.2), hand-written (no regex
//! dependency). Same language as `formats.ts`/`formats.py`; `fixtures/formats.json` pins it in
//! all three ports. The inputs are already ASCII: `schema.rs` refuses non-ASCII first.
//!
//! Implements: C-096

use crate::schema::Fmt;

/// Proposed reserved ids (SPEC §5.1.2): they are ids by shape but refused.
const RESERVED_IDS: [&str; 2] = ["constructor", "prototype"];

/// The prefixes a range comparator may carry, longest first.
const OPERATORS: [&str; 7] = [">=", "<=", ">", "<", "=", "^", "~"];

const fn is_id_byte(b: u8) -> bool {
    b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_' || b == b'-'
}

/// Whether `s` is an id: a-z, then up to 63 of a-z, 0-9, `_`, `-`; not reserved.
pub(crate) fn is_id(s: &str) -> bool {
    s.as_bytes().first().is_some_and(u8::is_ascii_lowercase)
        && s.len() <= 64
        && s.bytes().all(is_id_byte)
        && !RESERVED_IDS.contains(&s)
}

/// Whether `s` is a canonical decimal: `0`, or digits without a leading zero.
pub(crate) fn is_num(s: &str) -> bool {
    s == "0" || (!s.is_empty() && !s.starts_with('0') && s.bytes().all(|b| b.is_ascii_digit()))
}

fn is_word(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-')
}

/// A pre-release identifier: a canonical number, or a word with a non-digit.
fn is_pre(s: &str) -> bool {
    is_word(s) && (is_num(s) || !s.bytes().all(|b| b.is_ascii_digit()))
}

fn is_semver(s: &str) -> bool {
    let (rest, build) = s.split_once('+').map_or((s, None), |(r, b)| (r, Some(b)));
    let (core, pre) = rest.split_once('-').map_or((rest, None), |(c, p)| (c, Some(p)));
    core.split('.').count() == 3
        && core.split('.').all(is_num)
        && pre.is_none_or(|p| p.split('.').all(is_pre))
        && build.is_none_or(|b| b.split('.').all(is_word))
}

fn is_comparator(c: &str) -> bool {
    is_semver(OPERATORS.iter().find_map(|op| c.strip_prefix(op)).unwrap_or(c))
}

/// `a b || c`: `||`-separated sets of space-separated comparators (`>=1.3.0`, `^1.3.0`).
fn is_semver_range(s: &str) -> bool {
    s.split(" || ").all(|set| !set.is_empty() && set.split(' ').all(is_comparator))
}

/// The value of `s` if it is exactly `n` decimal digits.
fn fixed(s: &str, n: usize) -> Option<u32> {
    (s.len() == n && s.bytes().all(|b| b.is_ascii_digit())).then(|| s.parse().unwrap_or_default())
}

const fn days_in(year: u32, month: u32) -> u32 {
    if month == 2 {
        if year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) { 29 } else { 28 }
    } else if matches!(month, 4 | 6 | 9 | 11) {
        30
    } else {
        31
    }
}

/// `YYYY-MM-DDTHH:MM:SS[.frac](Z|±HH:MM)` with a real date (RFC 3339 §5.6).
#[expect(clippy::many_single_char_names, reason = "the RFC 3339 field names")]
fn is_timestamp(s: &str) -> bool {
    let Some((date, time)) = s.split_once(['T', 't']) else { return false };
    let (clock, offset) = time
        .strip_suffix(['Z', 'z'])
        .map_or_else(|| time.rsplit_once(['+', '-']).map_or(("", ""), |(c, o)| (c, o)), |c| (c, "00:00"));
    let (clock, fraction) = clock.split_once('.').map_or((clock, None), |(c, f)| (c, Some(f)));
    let mut d = date.split('-');
    let mut c = clock.split(':');
    let mut o = offset.split(':');
    let fields = [
        (d.next(), 4),
        (d.next(), 2),
        (d.next(), 2),
        (c.next(), 2),
        (c.next(), 2),
        (c.next(), 2),
        (o.next(), 2),
        (o.next(), 2),
    ]
    .map(|(part, n)| part.and_then(|p| fixed(p, n)));
    let [Some(y), Some(mo), Some(day), Some(h), Some(mi), Some(sec), Some(oh), Some(om)] = fields else {
        return false;
    };
    d.next().is_none()
        && c.next().is_none()
        && o.next().is_none()
        && fraction.is_none_or(|f| !f.is_empty() && f.bytes().all(|b| b.is_ascii_digit()))
        && (1..=12).contains(&mo)
        && (1..=days_in(y, mo)).contains(&day)
        && h <= 23
        && mi <= 59
        && sec <= 60
        && oh <= 23
        && om <= 59
}

const fn is_hex(b: u8) -> bool {
    b.is_ascii_digit() || matches!(b, b'a'..=b'f')
}

const fn is_base64(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'+' || b == b'/'
}

/// `sha256-` and 44 base64 characters for 32 bytes: 42 free, one with its low two bits zero, `=`.
fn is_integrity(s: &str) -> bool {
    match s.strip_prefix("sha256-").map(str::as_bytes) {
        Some([head @ .., last, b'=']) => {
            head.len() == 42 && head.iter().copied().all(is_base64) && b"AEIMQUYcgkosw048".contains(last)
        }
        _ => false,
    }
}

/// Whether `s` (non-empty, ASCII) has format `fmt`. `string` and `expr` accept any non-empty text.
pub(crate) fn matches(fmt: Fmt, s: &str) -> bool {
    match fmt {
        Fmt::String | Fmt::Expr => !s.is_empty(),
        Fmt::Id => is_id(s),
        Fmt::TargetId => s.split_once('/').is_some_and(|(p, m)| is_id(p) && is_id(m)),
        Fmt::CapabilityPath => s.split('.').all(is_id),
        Fmt::Semver => is_semver(s),
        Fmt::SemverRange => is_semver_range(s),
        Fmt::ProtocolVersion => s.split_once('.').is_some_and(|(a, b)| is_num(a) && is_num(b)),
        Fmt::Hash => s.strip_prefix("sha256:").is_some_and(|h| h.len() == 64 && h.bytes().all(is_hex)),
        Fmt::Integrity => is_integrity(s),
        Fmt::Timestamp => is_timestamp(s),
        Fmt::XKey => s.strip_prefix("x-").is_some_and(is_id),
        Fmt::ConfidenceRef => s == "native" || s.strip_prefix("portable/").is_some_and(is_id),
    }
}

#[cfg(test)]
#[expect(clippy::expect_used, clippy::indexing_slicing, reason = "tests: a bad fixture is a test failure")]
mod tests {
    use super::matches;
    use crate::schema::Fmt;
    use crate::schema_gen::format_desc;

    const ALL: [(&str, Fmt); 13] = [
        ("string", Fmt::String),
        ("expr", Fmt::Expr),
        ("id", Fmt::Id),
        ("target_id", Fmt::TargetId),
        ("capability_path", Fmt::CapabilityPath),
        ("semver", Fmt::Semver),
        ("semver_range", Fmt::SemverRange),
        ("protocol_version", Fmt::ProtocolVersion),
        ("hash", Fmt::Hash),
        ("integrity", Fmt::Integrity),
        ("timestamp", Fmt::Timestamp),
        ("x_key", Fmt::XKey),
        ("confidence_ref", Fmt::ConfidenceRef),
    ];

    fn json(rel: &str) -> serde_json::Value {
        let path = format!("{}/../../{rel}", env!("CARGO_MANIFEST_DIR"));
        serde_json::from_str(&std::fs::read_to_string(path).expect("fixture readable"))
            .expect("fixture JSON valid")
    }

    /// C-096: `fixtures/formats.json`, the same verdicts as `formats.ts` and `formats.py`.
    #[test]
    fn shared_verdicts() {
        let doc = json("fixtures/formats.json");
        let table = doc["formats"].as_object().expect("object");
        assert_eq!(table.len(), ALL.len());
        for (name, fmt) in ALL {
            for case in table[name].as_array().expect("array") {
                let value = case["value"].as_str().expect("string");
                assert_eq!(matches(fmt, value), case["ok"].as_bool().expect("bool"), "{name}: {value:?}");
            }
        }
    }

    /// Every format's `must be <desc>` text is the one in the schema source.
    #[test]
    fn descriptions_match_the_schema_source() {
        let doc = json("schema/urim-0.2.json");
        for (name, fmt) in ALL {
            assert_eq!(Some(format_desc(fmt)), doc["formats"][name].as_str(), "{name}");
        }
    }
}
