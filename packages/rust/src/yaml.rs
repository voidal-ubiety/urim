//! The YAML layer: text to a root mapping, plus the scalar rules every port shares.

use serde_norway::{Mapping, Value};

use crate::Problem;

/// Parse `text` as one YAML document whose root is a mapping.
///
/// A leading BOM is ignored (C-014). Collection keys anywhere make the document
/// invalid (C-023).
pub(crate) fn parse_root(text: &str) -> Result<Mapping, Problem> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    match serde_norway::from_str::<Value>(text) {
        Ok(v) if has_collection_key(&v) => Err(Problem::InvalidYaml),
        Ok(Value::Mapping(m)) => Ok(m),
        Ok(_) => Err(Problem::RootNotMapping),
        Err(_) => Err(Problem::InvalidYaml),
    }
}

/// The value as an integer, if it is one (`1.0` is a float, not an integer).
pub(crate) fn as_int(v: &Value) -> Option<i128> {
    match v {
        Value::Number(n) => n.as_i64().map(i128::from).or_else(|| n.as_u64().map(i128::from)),
        _ => None,
    }
}

/// The value as a string, if it is one.
pub(crate) fn as_str(v: &Value) -> Option<&str> {
    match v {
        Value::String(s) => Some(s.as_str()),
        _ => None,
    }
}

/// A sequence or mapping, looking through any tag (`!t [1]` is still a sequence).
fn is_collection(v: &Value) -> bool {
    match v {
        Value::Sequence(_) | Value::Mapping(_) => true,
        Value::Tagged(t) => is_collection(&t.value),
        _ => false,
    }
}

/// Mapping keys must be scalars. JS and Python cannot represent collection keys
/// faithfully, so every port rejects them.
fn has_collection_key(v: &Value) -> bool {
    match v {
        // A key that is not a collection is a (possibly tagged) scalar, so it
        // cannot contain a collection key itself; only values need recursion.
        Value::Mapping(m) => m.iter().any(|(k, val)| is_collection(k) || has_collection_key(val)),
        Value::Sequence(s) => s.iter().any(has_collection_key),
        Value::Tagged(t) => has_collection_key(&t.value),
        _ => false,
    }
}
