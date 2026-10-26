//! Urim: a contract language for decision models (pre-alpha).
//!
//! v0.0.1 provides [`check_file`], the logic behind `urim check <file>`. It validates a
//! hoshen lockfile or a contract's top-level shape. The behavior is specified in the
//! repository's `fixtures/README.md` and is identical to the TypeScript and Python ports.

use serde_norway::{Mapping, Value};

/// Package version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
/// Lockfile (`hoshen`) format versions this release can read.
pub const SUPPORTED_HOSHEN: &[i64] = &[1];

const CONTRACT_REQUIRED: [&str; 4] = ["contract", "version", "state", "questions"];
const NOT_URIM: &str =
    "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'";

/// Result of checking one file: `line` is the exact message the CLI prints.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CheckResult {
    pub ok: bool,
    pub line: String,
}

impl CheckResult {
    /// Process exit code: 0 when valid, 1 otherwise.
    pub fn exit_code(&self) -> i32 {
        if self.ok {
            0
        } else {
            1
        }
    }
}

fn fail(file: &str, problem: &str) -> CheckResult {
    CheckResult { ok: false, line: format!("{file}: error: {problem}") }
}

fn pass(file: &str, detail: &str) -> CheckResult {
    CheckResult { ok: true, line: format!("{file}: ok ({detail})") }
}

fn get<'a>(m: &'a Mapping, key: &str) -> Option<&'a Value> {
    m.get(Value::String(key.to_owned()))
}

fn as_int(v: &Value) -> Option<i128> {
    match v {
        Value::Number(n) if n.is_i64() => n.as_i64().map(i128::from),
        Value::Number(n) if n.is_u64() => n.as_u64().map(i128::from),
        _ => None,
    }
}

/// Mapping keys must be scalars (sequence/mapping keys are rejected as invalid YAML in
/// every implementation, since JS and Python cannot represent them faithfully).
fn has_collection_key(v: &Value) -> bool {
    match v {
        Value::Mapping(m) => m.iter().any(|(k, val)| {
            matches!(k, Value::Sequence(_) | Value::Mapping(_)) || has_collection_key(k) || has_collection_key(val)
        }),
        Value::Sequence(s) => s.iter().any(has_collection_key),
        Value::Tagged(t) => has_collection_key(&t.value),
        _ => false,
    }
}

/// Check YAML text; `file` is used only in the message.
pub fn check_text(file: &str, text: &str) -> CheckResult {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let root: Value = match serde_norway::from_str(text) {
        Ok(v) if !has_collection_key(&v) => v,
        _ => return fail(file, "invalid YAML"),
    };
    let root = match root {
        Value::Mapping(m) => m,
        _ => return fail(file, "root must be a mapping"),
    };

    if let Some(hoshen) = get(&root, "hoshen") {
        let Some(h) = as_int(hoshen) else {
            return fail(file, "hoshen must be an integer");
        };
        if !SUPPORTED_HOSHEN.iter().any(|s| i128::from(*s) == h) {
            let supported: Vec<String> = SUPPORTED_HOSHEN.iter().map(|s| s.to_string()).collect();
            return fail(
                file,
                &format!("unsupported hoshen version {h} (supported: {})", supported.join(", ")),
            );
        }
        return match get(&root, "urim") {
            None => fail(file, "missing required key(s): urim"),
            Some(Value::String(u)) => pass(file, &format!("lockfile, hoshen {h}, urim {u}")),
            Some(_) => fail(file, "urim must be a string"),
        };
    }

    let has_dctp = get(&root, "dctp").is_some();
    let has_urim = get(&root, "urim").is_some();
    if has_dctp || has_urim {
        if has_dctp && has_urim {
            return fail(file, "set only one of 'dctp' or 'urim'");
        }
        let key = if has_dctp { "dctp" } else { "urim" };
        let Some(Value::String(spec_version)) = get(&root, key) else {
            return fail(file, &format!("{key} must be a string"));
        };
        let missing: Vec<&str> =
            CONTRACT_REQUIRED.iter().copied().filter(|k| get(&root, k).is_none()).collect();
        if !missing.is_empty() {
            return fail(file, &format!("missing required key(s): {}", missing.join(", ")));
        }
        let Some(Value::String(id)) = get(&root, "contract") else {
            return fail(file, "contract must be a string");
        };
        let Some(Value::String(version)) = get(&root, "version") else {
            return fail(file, "version must be a string");
        };
        if !matches!(get(&root, "state"), Some(Value::Mapping(_))) {
            return fail(file, "state must be a mapping");
        }
        match get(&root, "questions") {
            Some(Value::Mapping(q)) if !q.is_empty() => {}
            _ => return fail(file, "questions must be a non-empty mapping"),
        }
        return pass(file, &format!("contract {id}@{version}, {key} {spec_version}"));
    }

    fail(file, NOT_URIM)
}

/// Read `path` (strict UTF-8) and check it.
pub fn check_file(path: &str) -> CheckResult {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(_) => return fail(path, "cannot read file"),
    };
    match String::from_utf8(bytes) {
        Ok(text) => check_text(path, &text),
        Err(_) => fail(path, "file is not valid UTF-8"),
    }
}
