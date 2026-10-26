//! Runs the shared cases in ../../fixtures/cases.json (repository checkout only).
use std::path::PathBuf;
use std::process::Command;

fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../fixtures")
}

fn cases() -> Vec<(String, i32, String)> {
    let text = std::fs::read_to_string(fixtures().join("cases.json")).expect("cases.json");
    let doc: serde_json::Value = serde_json::from_str(&text).expect("valid JSON");
    doc["cases"]
        .as_array()
        .expect("cases array")
        .iter()
        .map(|c| {
            (
                c["path"].as_str().unwrap().to_owned(),
                c["exit"].as_i64().unwrap() as i32,
                c["output"].as_str().unwrap().to_owned(),
            )
        })
        .collect()
}

#[test]
fn shared_cases() {
    let all = cases();
    assert!(all.len() >= 20, "expected the shared suite, found {}", all.len());
    for (rel, exit, output) in all {
        let path = fixtures().join(&rel).to_string_lossy().into_owned();
        let r = urim::check_file(&path);
        assert_eq!(r.exit_code(), exit, "exit for {rel}");
        assert_eq!(r.line, output.replace("{file}", &path), "line for {rel}");
    }
}

#[test]
fn cli_streams_and_exit_codes() {
    let bin = env!("CARGO_BIN_EXE_urim");
    let ok = Command::new(bin).args(["check"]).arg(fixtures().join("valid/minimal.lock")).output().unwrap();
    assert_eq!(ok.status.code(), Some(0));
    assert!(String::from_utf8_lossy(&ok.stdout).contains("ok (lockfile, hoshen 1, urim 0.1)"));
    assert!(ok.stderr.is_empty());
    let bad = Command::new(bin).args(["check"]).arg(fixtures().join("invalid/hoshen-unsupported.lock")).output().unwrap();
    assert_eq!(bad.status.code(), Some(1));
    assert!(bad.stdout.is_empty());
    assert!(String::from_utf8_lossy(&bad.stderr).contains("unsupported hoshen version 2"));
    assert_eq!(Command::new(bin).output().unwrap().status.code(), Some(2));
    let v = Command::new(bin).arg("--version").output().unwrap();
    assert_eq!(String::from_utf8_lossy(&v.stdout).trim(), "urim 0.0.1");
}
