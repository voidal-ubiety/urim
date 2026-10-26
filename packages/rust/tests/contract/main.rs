//! The living contract for the Rust port: one test per ID in the repository's
//! `CONTRACT.md`, driven by the shared JSON fixtures in `fixtures/`.
#![expect(
    clippy::expect_used,
    clippy::unwrap_used,
    clippy::indexing_slicing,
    clippy::print_stderr,
    reason = "test code: a failed expectation is a test failure"
)]

mod api;
mod cli;
mod divergences;
mod files;
mod support;
