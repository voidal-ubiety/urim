//! Urim: a contract language for decision models (pre-alpha).
//!
//! Version 0.0.1 provides the logic behind `urim check <file>`, which validates a hoshen 2
//! lockfile or a urim 0.2 contract against the closed schema of `schema/urim-0.2.json`. The behavior is catalogued in the
//! repository's `CONTRACT.md`, and the TypeScript and Python ports produce
//! byte-identical output.
//!
//! # Examples
//!
//! ```
//! let result = urim::check_text("urim.lock", "hoshen: 2\nurim: \"0.1\"\n");
//! assert_eq!(result.line(), "urim.lock: error: unsupported urim version 0.1 (supported: 0.2)");
//! assert_eq!(result.exit_code(), 1);
//!
//! let result = urim::check_text("urim.lock", "hoshen: 3\nurim: \"0.1\"\n");
//! assert_eq!(result.problem(), Some(&urim::Problem::UnsupportedHoshen { version: 3 }));
//! assert_eq!(result.to_string(), "urim.lock: error: unsupported hoshen version 3 (supported: 2)");
//! ```

mod check;
mod display;
mod formats;
mod jcs;
mod limits;
mod problem;
mod profile;
mod read;
mod rules;
mod schema;
#[rustfmt::skip]
mod schema_gen;
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
