//! C-001..C-007, C-012: the `urim` binary, driven by `fixtures/cli.json` (cwd = fixtures/).
use crate::support;

use std::process::{Command, Output};

fn run(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_urim"))
        .args(args)
        .current_dir(support::fixtures())
        .output()
        .expect("spawn urim")
}

fn assert_cli_cases(id: &str) {
    let cases = support::by_id("cli.json", id);
    assert!(!cases.is_empty(), "no cli cases tagged {id}");
    for case in &cases {
        let args: Vec<&str> = case["args"].as_array().unwrap().iter().map(|a| a.as_str().unwrap()).collect();
        let out = run(&args);
        assert_eq!(i64::from(out.status.code().unwrap()), case["exit"].as_i64().unwrap(), "exit {args:?}");
        assert_eq!(
            String::from_utf8(out.stdout).unwrap(),
            case["stdout"].as_str().unwrap(),
            "stdout {args:?}"
        );
        assert_eq!(
            String::from_utf8(out.stderr).unwrap(),
            case["stderr"].as_str().unwrap(),
            "stderr {args:?}"
        );
    }
}

macro_rules! cli_contract {
    ($($name:ident => $id:literal),+ $(,)?) => {
        $( #[test] fn $name() { assert_cli_cases($id); } )+

        #[test]
        fn c000_every_cli_case_id_has_a_rust_test() {
            let mut mine = vec![$($id.to_owned()),+];
            mine.sort();
            assert_eq!(mine, support::ids("cli.json"));
        }
    };
}

cli_contract! {
    c001_version => "C-001",
    c002_help => "C-002",
    c003_usage_error => "C-003",
    c004_ok_to_stdout => "C-004",
    c005_error_to_stderr => "C-005",
    c006_path_verbatim => "C-006",
}

#[test]
fn c007_binary_is_named_urim() {
    let out = run(&["--version"]);
    assert_eq!(String::from_utf8(out.stdout).unwrap(), format!("urim {}\n", urim::VERSION));
    let manifest = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml")).unwrap();
    assert!(manifest.contains("[[bin]]\nname = \"urim\""));
}

#[cfg(unix)]
#[test]
fn c012_permission_denied_is_cannot_read() {
    use std::os::unix::fs::PermissionsExt;
    let dir = std::env::temp_dir().join(format!("urim-c012-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let file = dir.join("locked.lock");
    std::fs::write(&file, "hoshen: 1\nurim: x\n").unwrap();
    std::fs::set_permissions(&file, std::fs::Permissions::from_mode(0o000)).unwrap();
    let readable = std::fs::read(&file).is_ok(); // root ignores permissions
    let path = file.to_str().unwrap();
    let out = run(&["check", path]);
    std::fs::remove_dir_all(&dir).unwrap();
    if readable {
        eprintln!("skipped: running as root");
        return;
    }
    assert_eq!(out.status.code(), Some(1));
    assert_eq!(String::from_utf8(out.stderr).unwrap(), format!("{path}: error: cannot read file\n"));
}

#[cfg(unix)]
#[test]
fn d012_non_utf8_path_argument() {
    use std::ffi::OsStr;
    use std::os::unix::ffi::OsStrExt;
    let dir = std::env::temp_dir().join(format!("urim-d012-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let name = OsStr::from_bytes(b"f\xff.lock");
    std::fs::write(dir.join(name), "hoshen: 1\nurim: x\n").unwrap();
    let out =
        Command::new(env!("CARGO_BIN_EXE_urim")).arg("check").arg(name).current_dir(&dir).output().unwrap();
    std::fs::remove_dir_all(&dir).unwrap();
    assert_eq!(out.status.code(), Some(0));
    assert_eq!(out.stdout, "f\u{fffd}.lock: ok (lockfile, hoshen 1, urim x)\n".as_bytes());
}
