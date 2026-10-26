//! Shared helpers for the contract tests: loads the repository's shared fixtures.
#![allow(dead_code, reason = "each test crate uses a different subset")]

use std::path::PathBuf;

use serde_json::Value;

/// Absolute path of the repository's `fixtures/` directory.
pub fn fixtures() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../fixtures")
}

/// The `cases` array of a shared JSON fixture file.
pub fn load(name: &str) -> Vec<Value> {
    let text = std::fs::read_to_string(fixtures().join(name)).expect("fixture JSON readable");
    let doc: Value = serde_json::from_str(&text).expect("fixture JSON valid");
    doc["cases"].as_array().expect("cases array").clone()
}

/// Cases in `name` tagged with contract `id`.
pub fn by_id(name: &str, id: &str) -> Vec<Value> {
    load(name).into_iter().filter(|c| c["id"] == id).collect()
}

/// Every distinct ID in `name`, sorted.
pub fn ids(name: &str) -> Vec<String> {
    let mut v: Vec<String> =
        load(name).iter().map(|c| c["id"].as_str().expect("id").to_owned()).collect();
    v.sort();
    v.dedup();
    v
}

/// Run `check_file` on a shared file case and compare the exit code and line.
pub fn assert_file_case(case: &Value, exit_key: &str, output_key: &str) {
    let rel = case["path"].as_str().expect("path");
    let path = fixtures().join(rel).to_string_lossy().into_owned();
    let r = urim::check_file(&path);
    let exit = case[exit_key].as_i64().expect("exit");
    let output = case[output_key].as_str().expect("output").replace("{file}", &path);
    assert_eq!(i64::from(r.exit_code()), exit, "exit for {rel}");
    assert_eq!(r.line, output, "line for {rel}");
    assert_eq!(r.ok, exit == 0, "ok for {rel}");
}
