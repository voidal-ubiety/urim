//! [`check_text`], [`check_file`] and their [`CheckResult`]: the lockfile and contract
//! schema checks that run on a root mapping from [`crate::profile`].
//!
//! Every string that reaches the output line (the file name and document values) goes
//! through [`sanitize`] (C-089).
//!
//! Implements: C-003, C-006, C-040, C-041, C-042, C-060, C-070, C-071, C-088, C-089, C-093..C-099

use std::fmt;
use std::path::Path;

use crate::display::sanitize;
use crate::jcs::integrity_of;
use crate::profile::{as_int, as_str, parse_root};
use crate::read::read_text;
use crate::rules::{contract_rules, lockfile_rules};
use crate::schema::{Fmt, Seg, check_string, validate};
use crate::schema_gen::{CONTRACT, LOCKFILE, PROTOCOL, format_desc};
use crate::value::{Mapping, Value};
use crate::{Problem, RENAMED_KEY, SUPPORTED_HOSHEN};

/// The outcome of checking one file: the single line the CLI prints, and why it failed.
///
/// # Examples
///
/// ```
/// let ok = urim::check_text("c.yaml", "urim: \"0.2\"\ncontract: c\nversion: 1.0.0\nstate: {s: {type: string}}\nquestions: {q: {type: yesno, instructions: Ok?}}\n");
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
/// let r = urim::check_text("c.yaml", "urim: \"0.2\"\ncontract: c\nversion: 1.0.0\nstate: {s: {type: string}}\nquestions: {q: {type: yesno, instructions: Ok?}}\n");
/// assert_eq!(r.line(), "c.yaml: ok (contract c@1.0.0, urim 0.2)");
///
/// let old = urim::check_text("c.yaml", "urim: \"0.1\"\n");
/// assert_eq!(old.line(), "c.yaml: error: unsupported urim version 0.1 (supported: 0.2)");
/// ```
pub fn check_text(file: &str, text: &str) -> CheckResult {
    match parse_root(text).and_then(detail) {
        Ok(detail) => CheckResult::pass(file, format_args!("{detail}")),
        Err(problem) => CheckResult::fail(file, problem),
    }
}

/// The text inside `ok (...)` for a valid document.
fn detail(root: Mapping) -> Result<String, Problem> {
    if root.contains_key(RENAMED_KEY) {
        return Err(Problem::RenamedKey);
    }
    let is_lockfile = root.contains_key("hoshen");
    let has_urim = root.contains_key("urim");
    let doc = Value::Mapping(root);
    if is_lockfile {
        lockfile(&doc, has_urim)
    } else if has_urim {
        contract(&doc)
    } else {
        Err(Problem::NotUrim)
    }
}

/// The `urim` gate (SPEC §5.1.1): a protocol version, then exactly the supported one.
fn urim_gate(doc: &Value) -> Result<(), Problem> {
    let fmt = Fmt::ProtocolVersion;
    let version = check_string(&[Seg::Key("urim")], doc.get("urim"), fmt, format_desc(fmt))?;
    if version == PROTOCOL { Ok(()) } else { Err(Problem::UnsupportedUrim { version: version.to_owned() }) }
}

fn lockfile(doc: &Value, has_urim: bool) -> Result<String, Problem> {
    let version = as_int(doc.get("hoshen")).ok_or(Problem::HoshenNotInteger)?;
    if version == 1 {
        return Err(Problem::HoshenNeverReleased);
    }
    if !SUPPORTED_HOSHEN.iter().any(|&s| i128::from(s) == version) {
        return Err(Problem::UnsupportedHoshen { version });
    }
    if !has_urim {
        return Err(Problem::MissingKeys { path: String::new(), keys: vec!["urim"] });
    }
    urim_gate(doc)?;
    validate(&LOCKFILE, doc)?;
    sealed(doc)?;
    lockfile_rules(doc)?;
    Ok(format!("lockfile, hoshen {version}, urim {PROTOCOL}"))
}

/// C-098: `integrity` is the hash of the rest of the document.
fn sealed(doc: &Value) -> Result<(), Problem> {
    let computed = integrity_of(doc)?;
    if as_str(doc.get("integrity")) != Some(computed.as_str()) {
        return Err(Problem::IntegrityMismatch { computed });
    }
    Ok(())
}

fn contract(doc: &Value) -> Result<String, Problem> {
    urim_gate(doc)?;
    validate(&CONTRACT, doc)?;
    contract_rules(doc)?;
    let field = |key| as_str(doc.get(key)).unwrap_or_default();
    Ok(format!("contract {}@{}, urim {PROTOCOL}", field("contract"), field("version")))
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

#[cfg(test)]
#[expect(clippy::expect_used, clippy::indexing_slicing, reason = "tests: a bad fixture is a test failure")]
mod tests {
    use super::sealed;
    use crate::profile::parse_root;
    use crate::value::Value;
    use crate::{Problem, check_file};

    /// `fixtures/cases.json` again, inside this crate. `cargo llvm-cov` scores a function by its
    /// best single test binary, not the union, so the private-path tests in this binary need the
    /// shared cases beside them (tests/contract runs the same cases per contract ID).
    #[test]
    fn shared_cases_in_crate() {
        let root = concat!(env!("CARGO_MANIFEST_DIR"), "/../../fixtures/");
        let text = std::fs::read_to_string(format!("{root}cases.json")).expect("fixture readable");
        let doc: serde_json::Value = serde_json::from_str(&text).expect("fixture JSON valid");
        for case in doc["cases"].as_array().expect("array") {
            let path = format!("{root}{}", case["path"].as_str().expect("string"));
            let r = check_file(&path);
            let want = case["output"].as_str().expect("string").replace("{file}", &path);
            assert_eq!(r.line(), want);
            assert_eq!(i64::from(r.exit_code()), case["exit"].as_i64().expect("int"));
        }
    }

    /// The lockfile schema admits only finite numbers, so `check` cannot reach this; the seal
    /// itself still refuses a document that has no canonical form rather than hashing a guess.
    #[test]
    fn a_non_finite_document_cannot_be_sealed() {
        let doc = Value::Mapping(parse_root("integrity: x\nn: [1, .inf]\n").expect("valid YAML"));
        assert_eq!(sealed(&doc), Err(Problem::NonFinite));
    }
}
