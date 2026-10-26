//! D-xxx: known cross-language divergences; pins this implementation's behavior.
mod support;

#[test]
fn d000_divergences_pin_rust_behavior() {
    let cases = support::load("divergences.json");
    assert!(!cases.is_empty());
    for case in &cases {
        let rust = &case["expect"]["rust"];
        let pinned = serde_json::json!({
            "path": case["path"], "exit": rust["exit"], "output": rust["output"],
        });
        support::assert_file_case(&pinned, "exit", "output");
    }
}
