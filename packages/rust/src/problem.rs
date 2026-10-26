//! [`Problem`]: why a document failed the check.

use std::fmt;

use crate::SUPPORTED_HOSHEN;

/// Why a file or document failed `urim check`.
///
/// The [`Display`](fmt::Display) text is the exact problem wording from `CONTRACT.md`.
/// It is what follows `<file>: error: ` on the CLI's output line.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum Problem {
    /// The file could not be opened or read (C-010, C-012).
    CannotRead,
    /// The file is not strict UTF-8 (C-011).
    NotUtf8,
    /// The text is not a single well-formed YAML 1.2 core-schema document (C-020..C-035).
    InvalidYaml,
    /// The document root is not a mapping (C-040).
    RootNotMapping,
    /// `hoshen` is present but is not an integer (C-041).
    HoshenNotInteger,
    /// `hoshen` is an integer this release cannot read (C-042).
    UnsupportedHoshen {
        /// The version found in the file.
        version: i128,
    },
    /// Required keys are absent, listed in contract order (C-043, C-053).
    MissingKeys(Vec<&'static str>),
    /// The named key is present but is not a string (C-044, C-052, C-054).
    NotAString(&'static str),
    /// Both `dctp` and `urim` are set in a contract (C-051).
    BothSpecKeys,
    /// `state` is not a mapping (C-055).
    StateNotMapping,
    /// `questions` is not a mapping, or it is empty (C-056).
    QuestionsEmpty,
    /// The document is neither a lockfile nor a contract (C-060).
    NotUrim,
}

impl fmt::Display for Problem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::CannotRead => f.write_str("cannot read file"),
            Self::NotUtf8 => f.write_str("file is not valid UTF-8"),
            Self::InvalidYaml => f.write_str("invalid YAML"),
            Self::RootNotMapping => f.write_str("root must be a mapping"),
            Self::HoshenNotInteger => f.write_str("hoshen must be an integer"),
            Self::UnsupportedHoshen { version } => {
                write!(f, "unsupported hoshen version {version} (supported: ")?;
                write_joined(f, SUPPORTED_HOSHEN)?;
                f.write_str(")")
            }
            Self::MissingKeys(keys) => {
                f.write_str("missing required key(s): ")?;
                write_joined(f, keys)
            }
            Self::NotAString(key) => write!(f, "{key} must be a string"),
            Self::BothSpecKeys => f.write_str("set only one of 'dctp' or 'urim'"),
            Self::StateNotMapping => f.write_str("state must be a mapping"),
            Self::QuestionsEmpty => f.write_str("questions must be a non-empty mapping"),
            Self::NotUrim => f.write_str(
                "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'",
            ),
        }
    }
}

impl std::error::Error for Problem {}

/// Write `items` separated by `", "` without building an intermediate `String`.
fn write_joined<T: fmt::Display>(f: &mut fmt::Formatter<'_>, items: &[T]) -> fmt::Result {
    for (i, item) in items.iter().enumerate() {
        if i > 0 {
            f.write_str(", ")?;
        }
        write!(f, "{item}")?;
    }
    Ok(())
}
