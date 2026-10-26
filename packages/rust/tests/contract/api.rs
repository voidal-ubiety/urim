//! C-070..C-073: the library API.
use urim::{Problem, SUPPORTED_HOSHEN, VERSION, check_file, check_text};

#[test]
fn c070_check_text_uses_file_only_in_message() {
    let r = check_text("no/such/file.lock", "hoshen: 1\nurim: \"0.1\"\n");
    assert!(r.is_ok());
    assert_eq!(r.line(), "no/such/file.lock: ok (lockfile, hoshen 1, urim 0.1)");
    assert_eq!(check_text("", "\u{feff}hoshen: 1\nurim: x\n").line(), ": ok (lockfile, hoshen 1, urim x)");
}

#[test]
fn c071_result_fields_and_exit_code() {
    let r = check_text("f", "[]");
    assert!(!r.is_ok());
    assert_eq!(r.line(), "f: error: root must be a mapping");
    assert_eq!(r.to_string(), r.line());
    assert_eq!(r.exit_code(), 1);
    let m = check_file("definitely/missing");
    assert_eq!(m.line(), "definitely/missing: error: cannot read file");
    assert_eq!(m.exit_code(), 1);
    let ok = check_text("f", "hoshen: 1\nurim: x\n");
    assert_eq!(ok.exit_code(), 0);
    assert_eq!(ok.problem(), None);
    assert_eq!(ok.into_line(), "f: ok (lockfile, hoshen 1, urim x)");
}

#[test]
fn c072_supported_hoshen_and_version() {
    assert_eq!(SUPPORTED_HOSHEN, &[1]);
    let manifest = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml")).unwrap();
    assert!(manifest.contains(&format!("\nversion = \"{VERSION}\"\n")));
}

/// Rust only: every failure carries a typed [`Problem`] whose `Display` is the message.
#[test]
fn c073_problem_is_typed_and_displays_the_message() {
    for case in crate::support::load("cases.json") {
        let path = crate::support::fixtures().join(case["path"].as_str().unwrap());
        let r = check_file(&path);
        if let Some(p) = r.problem() {
            assert_eq!(r.line(), format!("{}: error: {p}", path.display()));
            let as_error: &dyn std::error::Error = p;
            assert_eq!(as_error.to_string(), p.to_string());
        }
    }
    let p = check_text("f", "hoshen: 7\n").problem().cloned();
    assert_eq!(p, Some(Problem::UnsupportedHoshen { version: 7 }));
    let p = check_text("f", "dctp: x\n").problem().cloned();
    assert_eq!(p, Some(Problem::MissingKeys(vec!["contract", "version", "state", "questions"])));
}

/// A `fmt::Write` that fails after accepting `budget` bytes.
struct FailAfter {
    budget: usize,
}

impl std::fmt::Write for FailAfter {
    fn write_str(&mut self, s: &str) -> std::fmt::Result {
        self.budget = self.budget.checked_sub(s.len()).ok_or(std::fmt::Error)?;
        Ok(())
    }
}

/// `Display` for `Problem` propagates writer errors at every point instead of panicking.
#[test]
fn c073_problem_display_propagates_writer_errors() {
    use std::fmt::Write as _;
    let problems = [
        Problem::UnsupportedHoshen { version: 2 },
        Problem::MissingKeys(vec!["contract", "version"]),
        Problem::NotAString("urim"),
        Problem::NotUrim,
    ];
    for p in problems {
        let full = p.to_string().len();
        for budget in 0..full {
            assert!(write!(FailAfter { budget }, "{p}").is_err(), "{p:?} with budget {budget}");
        }
        assert!(write!(FailAfter { budget: full }, "{p}").is_ok());
    }
}
