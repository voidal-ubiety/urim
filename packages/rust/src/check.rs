//! [`check_text`], [`check_file`] and their [`CheckResult`]: the lockfile and contract
//! schema checks that run on a root mapping from [`crate::profile`].
//!
//! Every string that reaches the output line (the file name and document values) goes
//! through [`sanitize`] (C-089).
//!
//! Implements: C-003, C-006, C-040..C-044, C-050..C-057, C-060, C-070, C-071, C-088, C-089, C-093, C-094

use std::fmt;
use std::path::Path;

use crate::value::{Mapping, Value};

use crate::display::{is_invisible, sanitize};
use crate::profile::{as_int, as_str, parse_root};
use crate::read::read_text;
use crate::{Problem, RENAMED_KEY, SUPPORTED_HOSHEN};

/// Keys every contract must have, in the order they are reported when missing.
const CONTRACT_REQUIRED: [&str; 4] = ["contract", "version", "state", "questions"];

/// The outcome of checking one file: the single line the CLI prints, and why it failed.
///
/// # Examples
///
/// ```
/// let ok = urim::check_text("a.lock", "hoshen: 2\nurim: x\n");
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
        Self { line: format!("{}: ok ({detail})", sanitize(file)), problem: None }
    }

    fn fail(file: &str, problem: Problem) -> Self {
        Self { line: format!("{}: error: {problem}", sanitize(file)), problem: Some(problem) }
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
/// let r = urim::check_text("c.yaml", "urim: \"0.1\"\ncontract: c\nversion: 1.0.0\nstate: {}\nquestions: {q: {}}\n");
/// assert_eq!(r.line(), "c.yaml: ok (contract c@1.0.0, urim 0.1)");
/// ```
pub fn check_text(file: &str, text: &str) -> CheckResult {
    match parse_root(text).and_then(|root| detail(&root)) {
        Ok(detail) => CheckResult::pass(file, format_args!("{detail}")),
        Err(problem) => CheckResult::fail(file, problem),
    }
}

/// The text inside `ok (...)` for a valid document.
fn detail(root: &Mapping) -> Result<String, Problem> {
    if root.contains_key(RENAMED_KEY) {
        return Err(Problem::RenamedKey);
    }
    if let Some(hoshen) = root.get("hoshen") {
        return lockfile(root, hoshen);
    }
    root.get("urim").map_or(Err(Problem::NotUrim), |spec| contract(root, spec))
}

/// The string value of identifier `name`; invisible (C-088) and then non-ASCII (C-092)
/// characters are refused.
fn identifier<'a>(value: Option<&'a Value>, name: &'static str) -> Result<&'a str, Problem> {
    let s = value.and_then(as_str).ok_or(Problem::NotAString(name))?;
    if s.chars().any(is_invisible) {
        return Err(Problem::InvisibleIn(name));
    }
    if !s.is_ascii() {
        return Err(Problem::NonAsciiIn(name));
    }
    Ok(s)
}

fn lockfile(root: &Mapping, hoshen: &Value) -> Result<String, Problem> {
    let version = as_int(hoshen).ok_or(Problem::HoshenNotInteger)?;
    if version == 1 {
        return Err(Problem::HoshenNeverReleased);
    }
    if !SUPPORTED_HOSHEN.iter().any(|&s| i128::from(s) == version) {
        return Err(Problem::UnsupportedHoshen { version });
    }
    if !root.contains_key("urim") {
        return Err(Problem::MissingKeys(vec!["urim"]));
    }
    let urim = identifier(root.get("urim"), "urim")?;
    Ok(format!("lockfile, hoshen {version}, urim {}", sanitize(urim)))
}

/// `spec` is the value of the `urim` key.
fn contract(root: &Mapping, spec: &Value) -> Result<String, Problem> {
    let spec_version = identifier(Some(spec), "urim")?;
    let missing: Vec<&'static str> =
        CONTRACT_REQUIRED.into_iter().filter(|k| !root.contains_key(k)).collect();
    if !missing.is_empty() {
        return Err(Problem::MissingKeys(missing));
    }
    let id = identifier(root.get("contract"), "contract")?;
    let version = identifier(root.get("version"), "version")?;
    if !matches!(root.get("state"), Some(Value::Mapping(_))) {
        return Err(Problem::StateNotMapping);
    }
    if !matches!(root.get("questions"), Some(Value::Mapping(q)) if !q.is_empty()) {
        return Err(Problem::QuestionsEmpty);
    }
    Ok(format!("contract {}@{}, urim {}", sanitize(id), sanitize(version), sanitize(spec_version)))
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
    match read_text(path) {
        Ok(text) => check_text(&shown, &text),
        Err(problem) => CheckResult::fail(&shown, problem),
    }
}
