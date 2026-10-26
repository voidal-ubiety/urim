//! C-080, C-081, C-013, C-089: limits and file-type rules that need generated files, not fixtures.
use std::path::PathBuf;

use urim::{MAX_BYTES, MAX_DEPTH, Problem, check_file, check_text};

const LOCK: &str = "hoshen: 2\nurim: \"0.2\"\ngenerated_at: \"2026-10-26T10:00:00-04:00\"\ncompiler: {name: urim, version: 0.2.0}\nintegrity: \"sha256-RQmDCUPMRsURYEALq1dPcacebjwTGbE8W7juQwUmLzU=\"\ncontracts: {}\n";

/// A fresh, empty scratch directory unique to this test process and `name`.
fn scratch(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("urim-limits-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// A valid lockfile padded with a comment to exactly `size` bytes.
fn padded(size: usize) -> String {
    format!("{LOCK}#{}\n", "x".repeat(size.saturating_sub(LOCK.len()).saturating_sub(2)))
}

#[test]
fn c080_limits_are_exported() {
    assert_eq!((MAX_BYTES, MAX_DEPTH), (1_048_576, 64));
}

#[test]
fn c080_exactly_max_bytes_is_accepted_one_more_is_too_large() {
    let dir = scratch("size");
    let ok = dir.join("max.lock");
    std::fs::write(&ok, padded(MAX_BYTES)).unwrap();
    assert!(check_file(&ok).is_ok());
    let big = dir.join("big.lock");
    std::fs::write(&big, padded(MAX_BYTES + 1)).unwrap();
    assert_eq!(check_file(&big).problem(), Some(&Problem::TooLarge));
    assert_eq!(
        check_text("t", &padded(MAX_BYTES + 1)).line(),
        "t: error: file too large (max 1048576 bytes)"
    );
    // Bytes, not characters: two-byte characters count twice.
    let wide = format!("{LOCK}#{}", "é".repeat(MAX_BYTES / 2));
    assert_eq!(check_text("t", &wide).problem(), Some(&Problem::TooLarge));
    std::fs::remove_dir_all(dir).unwrap();
}

#[test]
fn c081_fifos_and_devices_are_refused_symlinks_followed() {
    let dir = scratch("types");
    let fifo = dir.join("fifo");
    assert!(std::process::Command::new("mkfifo").arg(&fifo).status().unwrap().success());
    assert_eq!(check_file(&fifo).line(), format!("{}: error: not a regular file", fifo.display()));
    assert_eq!(check_file("/dev/zero").problem(), Some(&Problem::NotRegularFile));
    assert_eq!(check_file("/dev/null").problem(), Some(&Problem::NotRegularFile));
    let target = dir.join("target.lock");
    std::fs::write(&target, LOCK).unwrap();
    let link = dir.join("link.lock");
    std::os::unix::fs::symlink(&target, &link).unwrap();
    assert_eq!(check_file(&link).line(), format!("{}: ok (lockfile, hoshen 2, urim 0.2)", link.display()));
    std::fs::remove_dir_all(dir).unwrap();
}

#[test]
fn c013_read_error_after_open_is_cannot_read() {
    // /proc/self/mem opens as a regular file but reading offset 0 fails with EIO.
    assert_eq!(check_file("/proc/self/mem").line(), "/proc/self/mem: error: cannot read file");
}

#[test]
fn c013_nul_in_the_path_is_cannot_read() {
    // Bug B-3 parity: the OS refuses a path with an embedded NUL before any open.
    let result = check_file("a\0b");
    assert!(!result.is_ok());
    assert_eq!(result.line(), "a\\u{0000}b: error: cannot read file");
}

#[test]
fn c089_unsafe_characters_in_the_file_name_are_escaped() {
    let line = check_text("a\u{1b}[31mb\u{202e}\u{85}", "[]").into_line();
    assert_eq!(line, "a\\u{001B}[31mb\\u{202E}\\u{0085}: error: root must be a mapping");
    assert_eq!(check_text("\u{e0041}", "[]").line(), "\\u{E0041}: error: root must be a mapping");
    // Undecodable path bytes are shown as U+FFFD, as in the other ports.
    let path = std::path::Path::new(<std::ffi::OsStr as std::os::unix::ffi::OsStrExt>::from_bytes(b"a\xffb"));
    assert_eq!(check_file(path).line(), "a\u{fffd}b: error: cannot read file");
}
