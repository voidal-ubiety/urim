//! [`Problem`]: why a document failed the check. The `Display` text of each variant is
//! the exact message from CONTRACT.md; `problem.ts` and `problem.py` hold the same strings.
//!
//! Implements: C-073 (and the message of every C-xxx failure listed on each variant)

use std::fmt;

use crate::limits::{MAX_BYTES, MAX_DEPTH};
use crate::schema_gen::PROTOCOL;
use crate::{RENAMED_KEY, SUPPORTED_HOSHEN};

/// Why a file or document failed `urim check`.
///
/// The [`Display`](fmt::Display) text is the exact problem wording from `CONTRACT.md`.
/// It is what follows `<file>: error: ` on the CLI's output line.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub enum Problem {
    /// The file could not be opened or read (C-010, C-012).
    CannotRead,
    /// The path is a directory, FIFO, device or other non-regular file (C-011, C-081).
    NotRegularFile,
    /// The input is larger than [`MAX_BYTES`] (C-080).
    TooLarge,
    /// The file is not strict UTF-8 (C-013).
    NotUtf8,
    /// The text is not a single well-formed YAML 1.2 core-schema document (C-020..C-035).
    InvalidYaml,
    /// Collections nest deeper than [`MAX_DEPTH`] (C-083).
    TooDeep,
    /// The document uses an anchor (`&a`) or an alias (`*a`) (C-084).
    AnchorOrAlias,
    /// The document has an explicit tag (`!!str`, `!t`, `!`) (C-085).
    Tag,
    /// A mapping key is `<<` (C-086).
    MergeKey,
    /// A mapping key contains an invisible or bidirectional-control character (C-087).
    InvisibleInKey,
    /// The value at the path contains an invisible or bidirectional-control character (C-088).
    InvisibleIn(String),
    /// The value at the path contains a non-ASCII character, such as a look-alike letter (C-092).
    NonAsciiIn(String),
    /// The document root is not a mapping (C-040).
    RootNotMapping,
    /// `hoshen` is present but is not an integer (C-041).
    HoshenNotInteger,
    /// `hoshen` is 1, a format that was never released (C-094).
    HoshenNeverReleased,
    /// `hoshen` is an integer this release cannot read (C-042).
    UnsupportedHoshen {
        /// The version found in the file.
        version: i128,
    },
    /// Required keys are absent, listed in schema order; `path` is empty at the root (C-043, C-095).
    MissingKeys {
        /// Where the keys are missing (empty at the root).
        path: String,
        /// The missing keys.
        keys: Vec<&'static str>,
    },
    /// The root has the pre-0.1 version key [`RENAMED_KEY`](crate::RENAMED_KEY), renamed to `urim` (C-093).
    RenamedKey,
    /// A value of the wrong type, format or range (C-096).
    MustBe {
        /// Where the value is.
        path: String,
        /// What it must be.
        expected: &'static str,
    },
    /// A key the closed schema does not define (C-095).
    UnknownKey(String),
    /// A mapping with a key that is not a string (C-095).
    NonStringKey(String),
    /// A mapping key of the wrong format (C-096).
    BadKey {
        /// Where the key is.
        path: String,
        /// What it must be.
        expected: &'static str,
    },
    /// A key that belongs to another variant of a tagged mapping (C-095).
    OnlyWhen {
        /// Where the key is.
        path: String,
        /// The tag key, such as `type`.
        field: &'static str,
        /// The tag values that allow the key.
        values: Vec<&'static str>,
    },
    /// A key removed in 0.2, or a key the position forbids, with the reason (C-095).
    Refused {
        /// Where the key is (for a forbidden key, the mapping that holds it).
        path: String,
        /// Why, starting with a verb phrase.
        reason: &'static str,
    },
    /// A repeated item in a list that must not repeat (C-096).
    Repeats {
        /// The repeat.
        path: String,
        /// The first occurrence.
        first: String,
    },
    /// An extension key with the reserved `x-urim-` prefix (C-095).
    ReservedExtension(String),
    /// A `urim` protocol version other than the supported one (C-041).
    UnsupportedUrim {
        /// The version found in the file.
        version: String,
    },
    /// The lockfile `integrity` is not the hash of its content (C-098).
    IntegrityMismatch {
        /// The integrity computed from the content.
        computed: String,
    },
    /// A number with no canonical JSON form (C-098).
    NonFinite,
    /// An experimental question type that `requires`/`prefers` do not declare (C-097).
    UndeclaredExperimental {
        /// Where the type is.
        path: String,
        /// The experimental type.
        kind: &'static str,
    },
    /// A reference to a question the contract does not declare (C-097).
    UnknownQuestion {
        /// Where the reference is.
        path: String,
        /// The name referenced.
        name: String,
    },
    /// A policy `when.answer` that the question cannot give (C-097).
    NotAnAnswer {
        /// Where the answer is.
        path: String,
        /// The question.
        question: String,
    },
    /// A capability in both `requires` and `prefers` (C-097).
    AlsoPreferred(String),
    /// A fallback naming an emulation that is not registered (C-097).
    NoEmulation {
        /// Where the name is.
        path: String,
        /// The emulation named.
        name: String,
    },
    /// An `active` or `standby` target that is not in the contract's `targets` (C-099).
    NotATarget {
        /// Where the target is.
        path: String,
        /// The target.
        value: String,
        /// The `targets` mapping it is missing from.
        targets: String,
    },
    /// The document is neither a lockfile nor a contract (C-060).
    NotUrim,
}

impl fmt::Display for Problem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::CannotRead => f.write_str("cannot read file"),
            Self::NotRegularFile => f.write_str("not a regular file"),
            Self::TooLarge => write!(f, "file too large (max {MAX_BYTES} bytes)"),
            Self::NotUtf8 => f.write_str("file is not valid UTF-8"),
            Self::TooDeep => write!(f, "nesting too deep (max depth {MAX_DEPTH})"),
            Self::AnchorOrAlias => f.write_str("anchors and aliases are not allowed"),
            Self::Tag => f.write_str("tags are not allowed"),
            Self::MergeKey => f.write_str("merge keys (<<) are not allowed"),
            Self::InvisibleInKey => {
                f.write_str("invisible or bidirectional control character in a mapping key")
            }
            Self::InvisibleIn(key) => write!(f, "invisible or bidirectional control character in {key}"),
            Self::NonAsciiIn(key) => write!(f, "non-ASCII character in {key}"),
            Self::InvalidYaml => f.write_str("invalid YAML"),
            Self::RootNotMapping => f.write_str("root must be a mapping"),
            Self::HoshenNotInteger => f.write_str("hoshen must be an integer"),
            Self::HoshenNeverReleased => {
                f.write_str("hoshen 1 was never released; the first lockfile format is hoshen 2")
            }
            Self::UnsupportedHoshen { version } => {
                write!(f, "unsupported hoshen version {version} (supported: ")?;
                write_joined(f, SUPPORTED_HOSHEN, ", ")?;
                f.write_str(")")
            }
            Self::MissingKeys { path, keys } => {
                f.write_str("missing required key(s)")?;
                if !path.is_empty() {
                    write!(f, " in {path}")?;
                }
                f.write_str(": ")?;
                write_joined(f, keys, ", ")
            }
            Self::RenamedKey => {
                write!(f, "the {RENAMED_KEY}: key was renamed to urim: before 0.1; replace it")
            }
            Self::MustBe { path, expected } => write!(f, "{path} must be {expected}"),
            Self::UnknownKey(path) => write!(f, "unknown key {path}"),
            Self::NonStringKey(path) => {
                write!(f, "{} has a non-string key", if path.is_empty() { "the root mapping" } else { path })
            }
            Self::BadKey { path, expected } => write!(f, "key {path} must be {expected}"),
            Self::OnlyWhen { path, field, values } => {
                write!(f, "{path} is only allowed when {field} is ")?;
                write_joined(f, values, " or ")
            }
            Self::Refused { path, reason } => write!(f, "{path} {reason}"),
            Self::Repeats { path, first } => write!(f, "{path} repeats {first}"),
            Self::ReservedExtension(path) => {
                write!(f, "{path} uses the reserved prefix x-urim- (SPEC §5.11.2)")
            }
            Self::UnsupportedUrim { version } => {
                write!(f, "unsupported urim version {version} (supported: {PROTOCOL})")
            }
            Self::IntegrityMismatch { computed } => {
                write!(f, "integrity does not match the file's content (computed {computed})")
            }
            Self::NonFinite => f.write_str("a number that is not finite has no canonical JSON form"),
            Self::UndeclaredExperimental { path, kind } => write!(
                f,
                "{path} has experimental type {kind}: declare question_types.{kind} in requires or prefers"
            ),
            Self::UnknownQuestion { path, name } => write!(f, "{path} names no declared question: {name}"),
            Self::NotAnAnswer { path, question } => {
                write!(f, "{path} is not an answer of question {question}")
            }
            Self::AlsoPreferred(path) => {
                write!(f, "{path} is also in prefers; a capability is required or preferred, not both")
            }
            Self::NoEmulation { path, name } => write!(f, "{path} names no registered emulation: {name}"),
            Self::NotATarget { path, value, targets } => {
                write!(f, "{path} is not a key of {targets}: {value}")
            }
            Self::NotUrim => f.write_str(
                "not a urim document: expected a lockfile with 'hoshen' or a contract with 'urim'",
            ),
        }
    }
}

impl std::error::Error for Problem {}

/// Write `items` separated by `sep` without building an intermediate `String`.
fn write_joined<T: fmt::Display>(f: &mut fmt::Formatter<'_>, items: &[T], sep: &str) -> fmt::Result {
    for (i, item) in items.iter().enumerate() {
        if i > 0 {
            f.write_str(sep)?;
        }
        write!(f, "{item}")?;
    }
    Ok(())
}
