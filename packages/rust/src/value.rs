//! Values built from the parser's events, with plain scalars resolved by the YAML 1.2 core
//! schema (§5.3), exactly as the JS and Python ports resolve them.
//!
//! Every node is kept: the closed schema (schema.rs) reads all of it, and the lockfile
//! integrity (jcs.rs) hashes all of it. Value errors are all `invalid YAML`: a duplicate key at any depth
//! (C-021), a collection key (C-023), an integer outside −2^63..2^64−1 (C-024).
//!
//! Resolution of a plain scalar (quoted and block scalars are always strings):
//! - null: `~`, `null`, `Null`, `NULL`, empty;
//! - bool: `true`/`True`/`TRUE`, `false`/`False`/`FALSE`; `yes`/`no`/`on`/`off` are strings
//!   (C-025);
//! - int: `[-+]?(0|[1-9][0-9]*)`, `0o[0-7]+`, `0x[0-9a-fA-F]+` (C-026). No sign on `0o`/`0x`, no
//!   `0b`, no `_`, no leading zeros: those are strings (C-027, bug B-5);
//! - float: `[-+]?(\.[0-9]+|[0-9]+\.[0-9]*)([eE][-+]?[0-9]+)?`, `[-+]?[0-9]+[eE][-+]?[0-9]+`,
//!   `[-+]?.inf` (three spellings) and `.nan` (three spellings) (C-028). An exponent too large
//!   for an `f64` is still a float (bug B-6);
//! - anything else is a string.
//!
//! Keys are equal when their type and value are equal (C-035): `1` and `0x1` collide, `1` and
//! `1.0` do not. `0.0` equals `-0.0`, and two NaN keys collide (D-011, as in Python).
//!
//! Implements: C-021, C-023, C-024, C-025, C-026, C-027, C-028, C-035

use std::collections::HashSet;

use saphyr_parser::{Event, ScalarStyle};

use crate::Problem;

const INT_MIN: i128 = -(1_i128 << 63);
const INT_MAX: i128 = (1_i128 << 64) - 1;

/// A built value.
#[derive(Debug)]
pub(crate) enum Value {
    Null,
    Bool(bool),
    Int(i128),
    Float(f64),
    String(String),
    Sequence(Vec<Self>),
    Mapping(Mapping),
}

/// The value an absent key reads as (see [`Value::get`]).
pub(crate) static NULL: Value = Value::Null;

impl Value {
    /// `self[key]`: a mapping's value, or a sequence's item when `key` is a decimal index;
    /// [`NULL`] when absent. After the closed schema no value is null, so null means absent.
    pub(crate) fn get(&self, key: &str) -> &Self {
        match self {
            Self::Mapping(map) => map.get(key),
            Self::Sequence(items) => key.parse::<usize>().ok().and_then(|i| items.get(i)),
            _ => None,
        }
        .unwrap_or(&NULL)
    }

    /// A mapping's string-keyed entries, or a sequence's items (with empty keys); else none.
    pub(crate) fn entries(&self) -> Vec<(&str, &Self)> {
        match self {
            Self::Mapping(map) => map.string_entries().unwrap_or_default(),
            Self::Sequence(items) => items.iter().map(|item| ("", item)).collect(),
            _ => Vec::new(),
        }
    }

    pub(crate) const fn is_null(&self) -> bool {
        matches!(self, Self::Null)
    }
}

/// Mapping entries in document order; keys are unique (C-021).
#[derive(Debug, Default)]
pub(crate) struct Mapping(Vec<(Value, Value)>);

impl Mapping {
    /// The value under the string key `key`.
    pub(crate) fn get(&self, key: &str) -> Option<&Value> {
        self.0.iter().find(|(k, _)| matches!(k, Value::String(s) if s == key)).map(|(_, v)| v)
    }

    pub(crate) fn contains_key(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// The entries in document order, or `None` if any key is not a string.
    pub(crate) fn string_entries(&self) -> Option<Vec<(&str, &Value)>> {
        self.0
            .iter()
            .map(|(k, v)| match k {
                Value::String(s) => Some((s.as_str(), v)),
                _ => None,
            })
            .collect()
    }
}

/// The identity of a scalar key for duplicate detection (C-021, C-035).
#[derive(PartialEq, Eq, Hash)]
enum Key {
    Null,
    Bool(bool),
    Int(i128),
    /// The bits of the float, with `-0.0` folded into `0.0` and every NaN into one NaN.
    Float(u64),
    String(String),
}

impl Key {
    /// `None` for a collection: collection keys are refused (C-023).
    fn of(value: &Value) -> Option<Self> {
        Some(match value {
            Value::Null => Self::Null,
            Value::Bool(b) => Self::Bool(*b),
            Value::Int(n) => Self::Int(*n),
            Value::Float(f) if f.is_nan() => Self::Float(f64::NAN.to_bits()),
            Value::Float(f) => Self::Float((f + 0.0).to_bits()),
            Value::String(s) => Self::String(s.clone()),
            Value::Sequence(_) | Value::Mapping(_) => return None,
        })
    }
}

/// One collection being built.
enum Frame {
    Sequence(Vec<Value>),
    Mapping { map: Mapping, seen: HashSet<Key>, key: Option<Value> },
}

impl Frame {
    fn finish(self) -> Value {
        match self {
            Self::Sequence(items) => Value::Sequence(items),
            Self::Mapping { map, .. } => Value::Mapping(map),
        }
    }
}

/// Build the document's root value from a well-formed, profile-clean event stream. An empty
/// document is null (C-030).
pub(crate) fn build(events: &[Event<'_>]) -> Result<Value, Problem> {
    let mut stack: Vec<Frame> = Vec::new();
    let mut root = Value::Null;
    for event in events {
        let done = match event {
            Event::Scalar(text, style, _, _) => resolve(text, *style)?,
            Event::SequenceStart(..) | Event::MappingStart(..) => {
                stack.push(if matches!(event, Event::SequenceStart(..)) {
                    Frame::Sequence(Vec::new())
                } else {
                    Frame::Mapping { map: Mapping::default(), seen: HashSet::new(), key: None }
                });
                continue;
            }
            // The parser balances every end with a start, so the stack is never empty here.
            Event::SequenceEnd | Event::MappingEnd => stack.pop().map_or(Value::Null, Frame::finish),
            // Profile-clean streams carry no aliases; the rest are not nodes.
            _ => continue,
        };
        match stack.last_mut() {
            None => root = done,
            Some(Frame::Sequence(items)) => items.push(done),
            Some(Frame::Mapping { map, seen, key }) => {
                if let Some(k) = key.take() {
                    map.0.push((k, done));
                } else {
                    // A collection key has no `Key`, so it is `invalid YAML` (C-021), as is a
                    // duplicate.
                    if !seen.insert(Key::of(&done).ok_or(Problem::InvalidYaml)?) {
                        return Err(Problem::InvalidYaml);
                    }
                    *key = Some(done);
                }
            }
        }
    }
    Ok(root)
}

fn resolve(text: &str, style: ScalarStyle) -> Result<Value, Problem> {
    if style != ScalarStyle::Plain {
        return Ok(Value::String(text.to_owned()));
    }
    Ok(match text {
        "" | "~" | "null" | "Null" | "NULL" => Value::Null,
        "true" | "True" | "TRUE" => Value::Bool(true),
        "false" | "False" | "FALSE" => Value::Bool(false),
        ".inf" | ".Inf" | ".INF" | "+.inf" | "+.Inf" | "+.INF" => Value::Float(f64::INFINITY),
        "-.inf" | "-.Inf" | "-.INF" => Value::Float(f64::NEG_INFINITY),
        ".nan" | ".NaN" | ".NAN" => Value::Float(f64::NAN),
        _ => {
            match int(text)? {
                Some(n) => Value::Int(n),
                // Every text `is_float` accepts parses; a huge exponent parses to infinity.
                None if is_float(text) => Value::Float(text.parse().unwrap_or_default()),
                None => Value::String(text.to_owned()),
            }
        }
    })
}

/// The integer `text` resolves to, if any; an integer outside −2^63..2^64−1 is `invalid YAML`.
fn int(text: &str) -> Result<Option<i128>, Problem> {
    let (radix, digits, negative) = if let Some(hex) = text.strip_prefix("0x") {
        (16, hex, false)
    } else if let Some(oct) = text.strip_prefix("0o") {
        (8, oct, false)
    } else {
        let (negative, unsigned) = match text.as_bytes().first() {
            Some(b'-') => (true, text.get(1..).unwrap_or_default()),
            Some(b'+') => (false, text.get(1..).unwrap_or_default()),
            _ => (false, text),
        };
        if unsigned.len() > 1 && unsigned.starts_with('0') {
            return Ok(None);
        }
        (10, unsigned, negative)
    };
    if digits.is_empty() || !digits.chars().all(|c| c.is_digit(radix)) {
        return Ok(None);
    }
    let mut n: i128 = 0;
    for c in digits.chars() {
        let digit = i128::from(c.to_digit(radix).unwrap_or_default());
        // Stop as soon as the magnitude leaves the range, so a megabyte of digits stays cheap.
        n = n
            .checked_mul(i128::from(radix))
            .and_then(|n| n.checked_add(digit))
            .filter(|&n| n <= INT_MAX)
            .ok_or(Problem::InvalidYaml)?;
    }
    let n = if negative { n.saturating_neg() } else { n };
    if n < INT_MIN {
        return Err(Problem::InvalidYaml);
    }
    Ok(Some(n))
}

/// Whether a plain scalar is a core-schema float in decimal or exponent form.
fn is_float(text: &str) -> bool {
    let body = text.strip_prefix(['-', '+']).unwrap_or(text);
    let (mantissa, exponent) = body.split_once(['e', 'E']).map_or((body, None), |(m, e)| (m, Some(e)));
    let (whole, fraction) = mantissa.split_once('.').map_or((mantissa, None), |(w, f)| (w, Some(f)));
    let digits = |s: &str| s.bytes().all(|b| b.is_ascii_digit());
    let mantissa_ok = fraction.map_or_else(
        || !whole.is_empty() && digits(whole) && exponent.is_some(),
        |f| digits(whole) && digits(f) && !(whole.is_empty() && f.is_empty()),
    );
    let exponent_ok = exponent.is_none_or(|e| {
        let e = e.strip_prefix(['-', '+']).unwrap_or(e);
        !e.is_empty() && digits(e)
    });
    mantissa_ok && exponent_ok
}
