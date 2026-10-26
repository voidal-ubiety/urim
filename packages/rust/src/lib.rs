//! Urim: a contract language for decision models (pre-alpha).
//!
//! Version 0.0.1 provides the logic behind `urim check <file>`, which validates a hoshen
//! lockfile or a contract's top-level shape. The behavior is catalogued in the
//! repository's `CONTRACT.md`, and the TypeScript and Python ports produce
//! byte-identical output.
//!
//! # Examples
//!
//! ```
//! let result = urim::check_text("urim.lock", "hoshen: 2\nurim: \"0.1\"\n");
//! assert!(result.is_ok());
//! assert_eq!(result.line(), "urim.lock: ok (lockfile, hoshen 2, urim 0.1)");
//! assert_eq!(result.exit_code(), 0);
//!
//! let result = urim::check_text("urim.lock", "hoshen: 3\nurim: \"0.1\"\n");
//! assert_eq!(result.problem(), Some(&urim::Problem::UnsupportedHoshen { version: 3 }));
//! assert_eq!(result.to_string(), "urim.lock: error: unsupported hoshen version 3 (supported: 2)");
//! ```

mod check;
mod display;
mod limits;
mod problem;
mod profile;
mod read;
mod value;

pub use check::{CheckResult, check_file, check_text};
pub use limits::{MAX_BYTES, MAX_DEPTH};
pub use problem::Problem;

/// Package version, as in `Cargo.toml`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Lockfile (`hoshen`) format versions this release can read.
pub const SUPPORTED_HOSHEN: &[i64] = &[2];

/// The pre-0.1 name of the `urim` key (C-093). Rejected, never read as an alias.
pub const RENAMED_KEY: &str = "dctp";
