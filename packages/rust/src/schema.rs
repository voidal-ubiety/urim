//! The closed-schema interpreter: checks a value against a node of the generated schema
//! (`schema_gen.rs`, from `schema/urim-0.2.json`). Same algorithm as `schema.ts`/`schema.py`;
//! CONTRACT.md C-095 states the order.
//!
//! Implements: C-088, C-092, C-095, C-096

use crate::Problem;
use crate::display::{is_invisible, sanitize};
use crate::formats::matches;
use crate::profile::as_str;
use crate::schema_gen::{EXTENSION, format_desc};
use crate::value::Value;

/// A string format of the type vocabulary (SPEC §5.1.2).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Fmt {
    String,
    Expr,
    Id,
    TargetId,
    CapabilityPath,
    Semver,
    SemverRange,
    ProtocolVersion,
    Hash,
    Integrity,
    Timestamp,
    XKey,
    ConfidenceRef,
}

/// A key of an object: its node and whether it is required.
#[derive(Debug)]
pub(crate) struct Field {
    pub(crate) name: &'static str,
    pub(crate) node: &'static Node,
    pub(crate) req: bool,
}

/// A tagged object: the value of `field` selects the extra fields of one variant.
#[derive(Debug)]
pub(crate) struct Tag {
    pub(crate) field: &'static str,
    pub(crate) variants: &'static [(&'static str, &'static [Field])],
}

/// A schema node. `desc` is the text after `must be`.
#[derive(Debug)]
pub(crate) enum Node {
    Str {
        fmt: Fmt,
        desc: &'static str,
    },
    Int {
        min: Option<i128>,
        desc: &'static str,
    },
    Num {
        min: Option<f64>,
        max: Option<f64>,
        min_open: bool,
        max_open: bool,
        desc: &'static str,
    },
    Bool {
        desc: &'static str,
    },
    Enum {
        values: &'static [&'static str],
        desc: &'static str,
    },
    List {
        items: &'static Self,
        min: usize,
        unique: bool,
        desc: &'static str,
    },
    Map {
        key: Fmt,
        value: &'static Self,
        min: usize,
        entries: &'static [Field],
        desc: &'static str,
    },
    Obj {
        fields: &'static [Field],
        ext: bool,
        tag: Option<Tag>,
        removed: &'static [(&'static str, &'static str)],
        desc: &'static str,
    },
    One {
        keys: &'static [Field],
        forbid: &'static [(&'static str, &'static str)],
        desc: &'static str,
    },
    Alt {
        options: &'static [Self],
        desc: &'static str,
    },
    Opaque {
        desc: &'static str,
    },
}

/// One step of a path: a mapping key or a sequence index.
#[derive(Debug, Clone, Copy)]
pub(crate) enum Seg<'a> {
    Key(&'a str),
    Index(usize),
}

fn at<'a>(path: &[Seg<'a>], seg: Seg<'a>) -> Vec<Seg<'a>> {
    let mut out = path.to_vec();
    out.push(seg);
    out
}

fn is_plain(key: &str) -> bool {
    !key.is_empty()
        && key.bytes().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'/' | b'-'))
}

/// `questions.team.options`, `targets["a b"]`, `levels[0]`; every key is sanitized (C-089).
pub(crate) fn path_text(path: &[Seg<'_>]) -> String {
    let mut out = String::new();
    for seg in path {
        match seg {
            Seg::Index(i) => {
                out.push('[');
                out.push_str(&i.to_string());
                out.push(']');
            }
            Seg::Key(key) if is_plain(key) => {
                if !out.is_empty() {
                    out.push('.');
                }
                out.push_str(key);
            }
            Seg::Key(key) => {
                let escaped = key.replace('\\', "\\\\").replace('"', "\\\"");
                out.push_str("[\"");
                out.push_str(&sanitize(&escaped));
                out.push_str("\"]");
            }
        }
    }
    out
}

fn must_be(path: &[Seg<'_>], expected: &'static str) -> Problem {
    Problem::MustBe { path: path_text(path), expected }
}

/// Refuse invisible (C-088), then non-ASCII (C-092) characters in a value of a strict format.
fn check_chars(path: &[Seg<'_>], s: &str) -> Result<(), Problem> {
    if s.chars().any(is_invisible) {
        return Err(Problem::InvisibleIn(path_text(path)));
    }
    if !s.is_ascii() {
        return Err(Problem::NonAsciiIn(path_text(path)));
    }
    Ok(())
}

/// A string of format `fmt` at `path`: invisible (C-088), then non-ASCII (C-092), then the format.
pub(crate) fn check_string<'v>(
    path: &[Seg<'_>],
    value: &'v Value,
    fmt: Fmt,
    desc: &'static str,
) -> Result<&'v str, Problem> {
    let s = as_str(value).filter(|s| !s.is_empty()).ok_or_else(|| must_be(path, desc))?;
    if !matches!(fmt, Fmt::String | Fmt::Expr) {
        check_chars(path, s)?;
    }
    if matches(fmt, s) { Ok(s) } else { Err(must_be(path, desc)) }
}

/// The entries of a mapping whose keys are all strings.
fn as_mapping<'v>(
    path: &[Seg<'_>],
    value: &'v Value,
    desc: &'static str,
) -> Result<Vec<(&'v str, &'v Value)>, Problem> {
    let Value::Mapping(map) = value else { return Err(must_be(path, desc)) };
    map.string_entries().ok_or_else(|| Problem::NonStringKey(path_text(path)))
}

fn lookup<'v>(entries: &[(&str, &'v Value)], key: &str) -> Option<&'v Value> {
    entries.iter().find(|(k, _)| *k == key).map(|(_, v)| *v)
}

/// The sign of `a - b` for finite numbers: -1, 0 or 1.
fn sign(a: f64, b: f64) -> i8 {
    i8::from(a > b).saturating_sub(i8::from(a < b))
}

/// An `i128` as the nearest `f64` (the same rounding as JS `Number(bigint)` and Python `float`).
pub(crate) fn int_to_f64(n: i128) -> f64 {
    n.to_string().parse().unwrap_or_default()
}

struct Obj {
    fields: &'static [Field],
    ext: bool,
    tag: Option<&'static Tag>,
    removed: &'static [(&'static str, &'static str)],
    desc: &'static str,
}

fn check_object(node: &Obj, value: &Value, path: &[Seg<'_>]) -> Result<(), Problem> {
    let map = as_mapping(path, value, node.desc)?;
    let tag_field = node.tag.map_or("", |t| t.field);
    let tag_value = lookup(&map, tag_field);
    let mut fields: Vec<&Field> = node.fields.iter().collect();
    // (key, variant) for every key of a variant the tag value does not select.
    let mut others: Vec<(&'static str, &'static str)> = Vec::new();
    if let Some(tag) = node.tag {
        if let Some(v) = tag_value {
            for f in node.fields.iter().filter(|f| f.name == tag.field) {
                check(f.node, v, &at(path, Seg::Key(f.name)))?;
            }
        }
        for (variant, extra) in tag.variants {
            if tag_value.is_none() || tag_value.and_then(as_str) == Some(variant) {
                fields.extend(extra.iter());
            } else {
                others.extend(extra.iter().map(|f| (f.name, *variant)));
            }
        }
    }
    for (key, _) in &map {
        if fields.iter().any(|f| f.name == *key) {
            continue;
        }
        let here = at(path, Seg::Key(key));
        if let Some((_, reason)) = node.removed.iter().find(|(k, _)| k == key) {
            return Err(Problem::Refused { path: path_text(&here), reason });
        }
        let values: Vec<&'static str> = others.iter().filter(|(k, _)| k == key).map(|(_, v)| *v).collect();
        if !values.is_empty() {
            return Err(Problem::OnlyWhen { path: path_text(&here), field: tag_field, values });
        }
        if node.ext && key.starts_with("x-") {
            check_extension_key(&here, key)?;
        } else {
            return Err(Problem::UnknownKey(path_text(&here)));
        }
    }
    // Without a tag value only the shared fields are required; the missing tag is reported.
    let required: Vec<&Field> =
        if tag_value.is_some() { fields.clone() } else { node.fields.iter().collect() };
    let missing: Vec<&'static str> =
        required.iter().filter(|f| f.req && lookup(&map, f.name).is_none()).map(|f| f.name).collect();
    if !missing.is_empty() {
        return Err(Problem::MissingKeys { path: path_text(path), keys: missing });
    }
    for (key, child) in &map {
        let here = at(path, Seg::Key(key));
        match fields.iter().find(|f| f.name == *key) {
            Some(f) if f.name == tag_field => {}
            Some(f) => check(f.node, child, &here)?,
            None => check(&EXTENSION, child, &here)?,
        }
    }
    Ok(())
}

/// An `x-<provider>` key at a position that allows one (SPEC §5.11.1, §5.11.2).
fn check_extension_key(path: &[Seg<'_>], key: &str) -> Result<(), Problem> {
    check_string(path, &Value::String(key.to_owned()), Fmt::XKey, format_desc(Fmt::XKey))?;
    if key.starts_with("x-urim-") {
        return Err(Problem::ReservedExtension(path_text(path)));
    }
    Ok(())
}

/// A mapping key of format `fmt`: the same order as a string value, with its own message.
/// Invisible characters in keys are already refused by the profile (C-087).
fn check_key(path: &[Seg<'_>], key: &str, fmt: Fmt) -> Result<(), Problem> {
    if !key.is_ascii() {
        return Err(Problem::NonAsciiIn(path_text(path)));
    }
    if !matches(fmt, key) {
        return Err(Problem::BadKey { path: path_text(path), expected: format_desc(fmt) });
    }
    if fmt == Fmt::XKey && key.starts_with("x-urim-") {
        return Err(Problem::ReservedExtension(path_text(path)));
    }
    Ok(())
}

/// The YAML kind a node accepts, for `alt` dispatch.
#[derive(PartialEq, Eq)]
enum Kind {
    String,
    Number,
    Boolean,
    Mapping,
    Sequence,
    Null,
}

const fn kind_of(value: &Value) -> Kind {
    match value {
        Value::String(_) => Kind::String,
        Value::Int(_) | Value::Float(_) => Kind::Number,
        Value::Bool(_) => Kind::Boolean,
        Value::Mapping(_) => Kind::Mapping,
        Value::Sequence(_) => Kind::Sequence,
        Value::Null => Kind::Null,
    }
}

const fn accepts(node: &Node) -> Kind {
    match node {
        Node::Str { .. } | Node::Enum { .. } => Kind::String,
        Node::Int { .. } | Node::Num { .. } => Kind::Number,
        Node::Bool { .. } => Kind::Boolean,
        Node::List { .. } => Kind::Sequence,
        Node::Map { .. } | Node::Obj { .. } | Node::One { .. } | Node::Opaque { .. } | Node::Alt { .. } => {
            Kind::Mapping
        }
    }
}

fn check_number(value: &Value, min: Option<f64>, max: Option<f64>, open: (bool, bool)) -> bool {
    let n = match value {
        Value::Int(i) => int_to_f64(*i),
        Value::Float(f) if f.is_finite() => *f,
        _ => return false,
    };
    min.is_none_or(|m| sign(n, m) >= i8::from(open.0)) && max.is_none_or(|m| sign(m, n) >= i8::from(open.1))
}

fn check_list(
    items: &'static Node,
    min: usize,
    unique: bool,
    value: &Value,
    path: &[Seg<'_>],
    desc: &'static str,
) -> Result<(), Problem> {
    let list = match value {
        Value::Sequence(list) if list.len() >= min => list,
        _ => return Err(must_be(path, desc)),
    };
    for (i, item) in list.iter().enumerate() {
        let here = at(path, Seg::Index(i));
        check(items, item, &here)?;
        let first = if unique { list.iter().position(|o| as_str(o) == as_str(item)).unwrap_or(i) } else { i };
        if first != i {
            return Err(Problem::Repeats {
                path: path_text(&here),
                first: path_text(&at(path, Seg::Index(first))),
            });
        }
    }
    Ok(())
}

fn check_map(
    key_fmt: Fmt,
    value_node: &'static Node,
    min: usize,
    entries: &[Field],
    value: &Value,
    path: &[Seg<'_>],
    desc: &'static str,
) -> Result<(), Problem> {
    let map = as_mapping(path, value, desc)?;
    if map.len() < min {
        return Err(must_be(path, desc));
    }
    for (key, child) in &map {
        let here = at(path, Seg::Key(key));
        if let Some(entry) = entries.iter().find(|f| f.name == *key) {
            check(entry.node, child, &here)?;
        } else {
            check_key(&here, key, key_fmt)?;
            check(value_node, child, &here)?;
        }
    }
    let missing: Vec<&'static str> =
        entries.iter().filter(|f| lookup(&map, f.name).is_none()).map(|f| f.name).collect();
    if !missing.is_empty() {
        return Err(Problem::MissingKeys { path: path_text(path), keys: missing });
    }
    Ok(())
}

fn check_one(
    keys: &[Field],
    forbid: &[(&str, &'static str)],
    value: &Value,
    path: &[Seg<'_>],
    desc: &'static str,
) -> Result<(), Problem> {
    let map = as_mapping(path, value, desc)?;
    for (key, _) in &map {
        if let Some((_, reason)) = forbid.iter().find(|(k, _)| k == key) {
            return Err(Problem::Refused { path: path_text(path), reason });
        }
        if !keys.iter().any(|f| f.name == *key) {
            return Err(Problem::UnknownKey(path_text(&at(path, Seg::Key(key)))));
        }
    }
    if map.len() != 1 {
        return Err(must_be(path, desc));
    }
    for f in keys {
        if let Some(child) = lookup(&map, f.name) {
            check(f.node, child, &at(path, Seg::Key(f.name)))?;
        }
    }
    Ok(())
}

fn require(ok: bool, path: &[Seg<'_>], desc: &'static str) -> Result<(), Problem> {
    if ok { Ok(()) } else { Err(must_be(path, desc)) }
}

fn check(node: &'static Node, value: &Value, path: &[Seg<'_>]) -> Result<(), Problem> {
    match node {
        Node::Str { fmt, desc } => check_string(path, value, *fmt, desc).map(|_| ()),
        Node::Int { min, desc } => {
            require(matches!(value, Value::Int(n) if min.is_none_or(|m| *n >= m)), path, desc)
        }
        Node::Num { min, max, min_open, max_open, desc } => {
            require(check_number(value, *min, *max, (*min_open, *max_open)), path, desc)
        }
        Node::Bool { desc } => require(matches!(value, Value::Bool(_)), path, desc),
        Node::Enum { values, desc } => {
            require(as_str(value).is_some_and(|s| values.contains(&s)), path, desc)
        }
        Node::List { items, min, unique, desc } => check_list(items, *min, *unique, value, path, desc),
        Node::Map { key, value: v, min, entries, desc } => {
            check_map(*key, v, *min, entries, value, path, desc)
        }
        Node::Obj { fields, ext, tag, removed, desc } => {
            check_object(&Obj { fields, ext: *ext, tag: tag.as_ref(), removed, desc }, value, path)
        }
        Node::One { keys, forbid, desc } => check_one(keys, forbid, value, path, desc),
        Node::Alt { options, desc } => {
            let kind = kind_of(value);
            let option = options.iter().find(|o| accepts(o) == kind).ok_or_else(|| must_be(path, desc))?;
            check(option, value, path)
        }
        Node::Opaque { desc } => require(!as_mapping(path, value, desc)?.is_empty(), path, desc),
    }
}

/// Check `value` (a document root) against `node`: the first problem, if any.
pub(crate) fn validate(node: &'static Node, value: &Value) -> Result<(), Problem> {
    check(node, value, &[])
}

#[cfg(test)]
mod tests {
    use super::{Kind, Node, accepts};

    /// `alt` picks an option by the YAML kind it accepts. Today's schema puts no list in an `alt`,
    /// so this arm is reached only here (the JS and Python ports use a lookup table).
    #[test]
    fn a_list_accepts_a_sequence() {
        static ITEM: Node = Node::Bool { desc: "true or false" };
        let list = Node::List { items: &ITEM, min: 0, unique: false, desc: "a sequence" };
        assert!(matches!(accepts(&list), Kind::Sequence));
    }
}
