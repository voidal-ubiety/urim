//! C-070..C-072: the library API.
use urim::{check_file, check_text, CheckResult, SUPPORTED_HOSHEN, VERSION};

#[test]
fn c070_check_text_uses_file_only_in_message() {
    let r = check_text("no/such/file.lock", "hoshen: 1\nurim: \"0.1\"\n");
    assert_eq!(
        r,
        CheckResult { ok: true, line: "no/such/file.lock: ok (lockfile, hoshen 1, urim 0.1)".into() }
    );
    assert_eq!(check_text("", "\u{feff}hoshen: 1\nurim: x\n").line, ": ok (lockfile, hoshen 1, urim x)");
}

#[test]
fn c071_result_fields_and_exit_code() {
    let r = check_text("f", "[]");
    assert_eq!(r, CheckResult { ok: false, line: "f: error: root must be a mapping".into() });
    assert_eq!(r.exit_code(), 1);
    let m = check_file("definitely/missing");
    assert_eq!(m.line, "definitely/missing: error: cannot read file");
    assert_eq!(m.exit_code(), 1);
    assert_eq!(check_text("f", "hoshen: 1\nurim: x\n").exit_code(), 0);
}

#[test]
fn c072_supported_hoshen_and_version() {
    assert_eq!(SUPPORTED_HOSHEN, &[1]);
    let manifest = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml")).unwrap();
    assert!(manifest.contains(&format!("\nversion = \"{VERSION}\"\n")));
}
