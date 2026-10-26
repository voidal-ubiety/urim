//! Reading a file safely: regular files only, bounded size, strict UTF-8.
//!
//! The file is opened first (non-blocking on Unix, so a FIFO cannot hang the open) and the
//! *opened handle* is inspected, so there is no stat-then-open race on the path.
//!
//! Implements: C-010, C-011, C-012, C-013, C-080, C-081

use std::fs::{File, OpenOptions};
use std::io::Read as _;
use std::path::Path;

use crate::Problem;
use crate::limits::MAX_BYTES;

#[cfg(target_os = "linux")]
const O_NONBLOCK: i32 = 0o4000;
#[cfg(all(unix, not(target_os = "linux")))]
const O_NONBLOCK: i32 = 0x0004; // macOS and the BSDs

fn open(path: &Path) -> std::io::Result<File> {
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    std::os::unix::fs::OpenOptionsExt::custom_flags(&mut options, O_NONBLOCK);
    options.open(path)
}

/// Read `path` as strict UTF-8 text within [`MAX_BYTES`].
///
/// The size is enforced by reading at most one byte past the limit rather than by
/// trusting the metadata length, which is wrong for `/proc` files and for files that
/// grow while being read. A handle whose metadata cannot be read is treated as not regular.
pub(crate) fn read_text(path: &Path) -> Result<String, Problem> {
    let file = open(path).map_err(|_| Problem::CannotRead)?;
    if !file.metadata().is_ok_and(|m| m.is_file()) {
        return Err(Problem::NotRegularFile);
    }
    let mut bytes = Vec::new();
    let limit = u64::try_from(MAX_BYTES).unwrap_or(u64::MAX).saturating_add(1);
    if file.take(limit).read_to_end(&mut bytes).is_err() {
        return Err(Problem::CannotRead);
    }
    if bytes.len() > MAX_BYTES {
        return Err(Problem::TooLarge);
    }
    String::from_utf8(bytes).map_err(|_| Problem::NotUtf8)
}
