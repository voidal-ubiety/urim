//! [`check_text`], [`check_file`] and their [`CheckResult`].

use std::fmt;
use std::path::Path;

use serde_norway::{Mapping, Value};

use crate::yaml::{as_int, as_str, parse_root};
use crate::{Problem, SUPPORTED_HOSHEN};

/// Keys every contract must have, in the order they are reported when missing.
const CONTRACT_REQUIRED: [&str; 4] = ["contract", "version", "state", "questions"];

/// The outcome of checking one file: the single line the CLI prints, and why it failed.
///
/// # Examples
///
/// ```
/// let ok = urim::check_text("a.lock", "hoshen: 1\nurim: x\n");
/// assert_eq!((ok.is_ok(), ok.exit_code()), (true, 0));
///
/// let bad = urim::check_text("a.lock", "[]");
/// assert_eq!(bad.problem(), Some(&urim::Problem::RootNotMapping));
/// assert_eq!(bad.line(), "a.lock: error: root must be a mapping");
/// assert_eq!(bad.exit_code(), 1);
/// ```
#[derive(Debug, Clone, PartialEq, Eq)]
#[must_use]
pub struct CheckResult {
    line: String,
    problem: Option<Problem>,
}

impl CheckResult {
    fn pass(file: &str, detail: fmt::Arguments<'_>) -> Self {
        Self { line: format!("{file}: ok ({detail})"), problem: None }
    }

    fn fail(file: &str, problem: Problem) -> Self {
        Self { line: format!("{file}: error: {problem}"), problem: Some(problem) }
    }

    /// Whether the document passed.
    #[must_use]
    pub const fn is_ok(&self) -> bool {
        self.problem.is_none()
    }

    /// The exact line the CLI prints: to stdout when ok, to stderr otherwise.
    #[must_use]
    pub fn line(&self) -> &str {
        &self.line
    }

    /// Why the check failed, or `None` when it passed.
    #[must_use]
    pub const fn problem(&self) -> Option<&Problem> {
        self.problem.as_ref()
    }

    /// The process exit code for this result: 0 when ok, 1 otherwise (C-003).
    #[must_use]
    pub const fn exit_code(&self) -> u8 {
        if self.is_ok() { 0 } else { 1 }
    }

    /// Consume the result and return its line.
    #[must_use]
    pub fn into_line(self) -> String {
        self.line
    }
}

impl fmt::Display for CheckResult {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.line)
    }
}

/// Check YAML `text`. `file` is used only in the message (C-070).
///
/// # Examples
///
/// ```
/// let r = urim::check_text("c.yaml", "dctp: \"0.1\"\ncontract: c\nversion: 1.0.0\nstate: {}\nquestions: {q: {}}\n");
/// assert_eq!(r.line(), "c.yaml: ok (contract c@1.0.0, dctp 0.1)");
/// ```
pub fn check_text(file: &str, text: &str) -> CheckResult {
    let root = match parse_root(text) {
        Ok(root) => root,
        Err(problem) => return CheckResult::fail(file, problem),
    };
    if let Some(hoshen) = root.get("hoshen") {
        return check_lockfile(file, &root, hoshen);
    }
    match (root.get("dctp"), root.get("urim")) {
        (Some(_), Some(_)) => CheckResult::fail(file, Problem::BothSpecKeys),
        (Some(spec), None) => check_contract(file, &root, ("dctp", spec)),
        (None, Some(spec)) => check_contract(file, &root, ("urim", spec)),
        (None, None) => CheckResult::fail(file, Problem::NotUrim),
    }
}

fn check_lockfile(file: &str, root: &Mapping, hoshen: &Value) -> CheckResult {
    let Some(version) = as_int(hoshen) else {
        return CheckResult::fail(file, Problem::HoshenNotInteger);
    };
    if !SUPPORTED_HOSHEN.iter().any(|&s| i128::from(s) == version) {
        return CheckResult::fail(file, Problem::UnsupportedHoshen { version });
    }
    let Some(urim) = root.get("urim") else {
        return CheckResult::fail(file, Problem::MissingKeys(vec!["urim"]));
    };
    let Some(urim) = as_str(urim) else {
        return CheckResult::fail(file, Problem::NotAString("urim"));
    };
    CheckResult::pass(file, format_args!("lockfile, hoshen {version}, urim {urim}"))
}

/// `key` is the spec-version key that is present (`dctp` or `urim`) and its value.
fn check_contract(file: &str, root: &Mapping, key: (&'static str, &Value)) -> CheckResult {
    let Some(spec_version) = as_str(key.1) else {
        return CheckResult::fail(file, Problem::NotAString(key.0));
    };
    let missing: Vec<&'static str> =
        CONTRACT_REQUIRED.into_iter().filter(|k| !root.contains_key(*k)).collect();
    if !missing.is_empty() {
        return CheckResult::fail(file, Problem::MissingKeys(missing));
    }
    let Some(id) = root.get("contract").and_then(as_str) else {
        return CheckResult::fail(file, Problem::NotAString("contract"));
    };
    let Some(version) = root.get("version").and_then(as_str) else {
        return CheckResult::fail(file, Problem::NotAString("version"));
    };
    if !matches!(root.get("state"), Some(Value::Mapping(_))) {
        return CheckResult::fail(file, Problem::StateNotMapping);
    }
    if !matches!(root.get("questions"), Some(Value::Mapping(q)) if !q.is_empty()) {
        return CheckResult::fail(file, Problem::QuestionsEmpty);
    }
    CheckResult::pass(file, format_args!("contract {id}@{version}, {} {spec_version}", key.0))
}

/// Read the file at `path` (strict UTF-8) and check it.
///
/// The message names the path exactly as given (C-006); a path that is not valid
/// Unicode is shown lossily.
///
/// # Examples
///
/// ```
/// let r = urim::check_file("no/such/file.lock");
/// assert_eq!(r.problem(), Some(&urim::Problem::CannotRead));
/// assert_eq!(r.line(), "no/such/file.lock: error: cannot read file");
/// ```
pub fn check_file(path: impl AsRef<Path>) -> CheckResult {
    let path = path.as_ref();
    let shown = path.to_string_lossy();
    let Ok(bytes) = std::fs::read(path) else {
        return CheckResult::fail(&shown, Problem::CannotRead);
    };
    let Ok(text) = String::from_utf8(bytes) else {
        return CheckResult::fail(&shown, Problem::NotUtf8);
    };
    check_text(&shown, &text)
}
