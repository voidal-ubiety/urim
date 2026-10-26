//! Hostile-input limits shared by every port. Values must match `limits.ts` and
//! `limits.py`. They are listed in SECURITY.md and checked by C-080 and C-083.
//!
//! Implements: C-080, C-083

/// Largest accepted input in bytes (1 MiB). Anything larger is rejected before
/// it is fully read (C-080).
pub const MAX_BYTES: usize = 1_048_576;

/// Deepest accepted nesting of collections; the root mapping is depth 1 (C-083).
pub const MAX_DEPTH: usize = 64;
