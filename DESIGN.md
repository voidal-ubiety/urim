# Design

How the three ports of `urim check` are built, and why. Behavior is defined by
[CONTRACT.md](CONTRACT.md) and the spec ([spec/SPEC.md](spec/SPEC.md)); this file covers
structure, data, cost and deliberate deviations. Decisions have records under
[docs/adr/](docs/adr/).

## 1. Layout

The same concern lives in a module with the same name in every port.

| Concern | JS (`packages/js`) | Python (`packages/python`) | Rust (`packages/rust`) |
|---|---|---|---|
| Public API surface | `src/index.ts` | `src/urim/__init__.py` | `src/lib.rs` |
| Check pipeline (lockfile / contract) | `src/check.ts` | `src/urim/check.py` | `src/check.rs` |
| Safe file read (regular file, size bound, strict UTF-8) | `src/read.ts` | `src/urim/read.py` | `src/read.rs` |
| Urim YAML profile (text to root) | `src/profile.ts` | `src/urim/profile.py` | `src/profile.rs`, `src/value.rs` |
| Hostile-input limits | `src/limits.ts` | `src/urim/limits.py` | `src/limits.rs` |
| Closed-schema interpreter | `src/schema.ts`, `src/node.ts` | `src/urim/schema.py`, `node.py` | `src/schema.rs` |
| Generated schema data (`scripts/gen-schema`, do not edit) | `src/schema.gen.ts` | `src/urim/schema_gen.py` | `src/schema_gen.rs` |
| String formats (SPEC §5.1.2) | `src/formats.ts` | `src/urim/formats.py` | `src/formats.rs` |
| Cross-field rules (C-097, C-099) | `src/rules.ts` | `src/urim/rules.py` | `src/rules.rs` |
| RFC 8785 JCS and the lockfile seal (C-098) | `src/jcs.ts` | `src/urim/jcs.py` | `src/jcs.rs` |
| Failure messages | `src/problem.ts` | `src/urim/problem.py` | `src/problem.rs` (`Problem` enum) |
| Output sanitization | `src/display.ts` | `src/urim/display.py` | `src/display.rs` |
| CLI | `src/cli.ts` (bin `urim`) | `src/urim/cli.py`, `__main__.py` | `src/main.rs` (bin `urim`) |
| Contract tests | `test/*.test.mjs` | `tests/test_*.py` | `tests/contract/*.rs` (one test crate), plus unit tests in `formats.rs`, `jcs.rs`, `check.rs` |

Rust uses a lib/bin split: `main.rs` only parses argv, writes one line and returns an
`ExitCode`; all logic is in the library. The Rust tests are one integration-test crate
(`tests/contract/main.rs` plus modules) so they link once and share `support.rs`.

## 2. Data flow and structures

```
path ─read bytes─▶ strict UTF-8 ─strip BOM─▶ YAML profile (1 document, core schema, limits)
     ─▶ root mapping ─▶ renamed key? ── error (C-093)
                       ├ "hoshen" present? ── hoshen gate ─▶ urim gate ─▶ closed schema ─▶ seal (JCS) ─▶ lockfile rules
                       └ "urim" present?   ── urim gate ─▶ closed schema ─▶ contract rules
                                                                          ─▶ CheckResult
```

* **Result:** each port returns a value with the printed line and ok/failed status.
  * JS has `{ ok, line }`.
  * Python has a frozen dataclass `CheckResult(ok, line)`.
  * Rust has an opaque `CheckResult` with `is_ok()`, `line()`, `problem()`, `exit_code() -> u8` and `into_line()`. Its `Problem` is a `#[non_exhaustive]` error enum whose `Display` is the message (C-073).
* **Mappings:**
  * JS: the `yaml` library's document tree, then plain JS values.
  * Python: `dict`, built by a `SafeLoader` subclass with core-schema resolvers.
  * Rust: `value::Mapping`, the entries in document order, built from saphyr-parser events by `src/value.rs` (no DOM or serde layer). Duplicate keys are found with a hash set while building. Key lookups scan the entries with a `&str`, without allocating.
* **Integers:** all three read integers losslessly. JS uses `bigint`, Python `int`, and Rust `i128`. Leading-zero integers stay strings (see CONTRACT.md).

## 3. Complexity

Let *n* be the input size in bytes.

| Step | Time | Extra memory |
|---|---|---|
| read + UTF-8 validation | O(n) | O(n) |
| YAML parse | O(n) for the libraries' normal inputs (see note) | O(n) |
| closed-schema walk | each value is visited once; key checks per mapping depend on the port's map type (not measured here) | O(depth) for the recursion |
| JCS + SHA-256 (lockfiles only) | O(n log n) worst case: each mapping's keys are sorted; the hash is O(n) | O(n) for the canonical text |

Note: the libraries' worst cases are not linear. Deep flow nesting was superlinear in
unsafe-libyaml-norway (no longer used), and PyYAML and JS `yaml` recurse. Those inputs are bounded by the
Urim YAML profile's size and depth limits (SECURITY.md). Benchmarks are in
`packages/rust/benches/`.

## 4. API changes in this refactor (behavior unchanged)

* **Rust:**
  * `CheckResult` fields became private behind accessors, and it gained `problem()` and `Display`.
  * `exit_code()` now returns `u8`, which `ExitCode::from` takes directly.
  * `check_file` takes `impl AsRef<Path>`.
  * The crate is edition 2024, with MSRV 1.85 checked in verify.sh.
* **Rust `main`:**
  * It reads `args_os`, so non-UTF-8 argv can no longer panic. A non-UTF-8 path is opened as given and shown lossily (D-012 records how JS differs).
  * It writes with `writeln!` and ignores a closed pipe instead of panicking like `println!`. The exit code still carries the result.
* **Python:** `check_text` is exported from the package.
* **JS:** `noUncheckedIndexedAccess` and the other strict flags are on, and indexing became destructuring.

## 5. Lint configuration

* **JS:**
  * `tsc` runs with `strict` plus `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitReturns`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUnused*`, `verbatimModuleSyntax` and `forceConsistentCasingInFileNames`.
  * Biome 2 uses its recommended rules, formats, and runs `biome ci`.
* **Python:**
  * `ruff check` has a wide rule set (see `pyproject.toml`; it includes `S` bandit, `ANN`, `D` pydocstyle, `PL`, `PTH`, `FBT` and `T20`). `ruff format` checks formatting.
  * `mypy --strict` checks both `src` and `tests`, with `warn_unreachable`.
* **Rust** (`[lints]` in `Cargo.toml`; clippy runs with `-D warnings`):
  * rustc: `unsafe_code = forbid`, plus warnings for `missing_docs`, `missing_debug_implementations`, `unreachable_pub`, `unused_qualifications` and `rust_2018_idioms`.
  * clippy groups: `pedantic`, `nursery` and `cargo`.
  * clippy restriction lints: `unwrap_used`, `expect_used`, `panic`, `indexing_slicing`, `string_slice`, `arithmetic_side_effects`, `as_conversions`, `print_stdout`, `print_stderr`, `dbg_macro`, `todo`, `unimplemented`, `allow_attributes` and `allow_attributes_without_reason`.
  * One group lint is turned off: `redundant_pub_crate` (nursery) contradicts rustc's `unreachable_pub`. We keep `unreachable_pub`, so items in private modules are `pub(crate)`.
  * `RUSTDOCFLAGS="-D warnings" cargo doc`; doctests run in verify.sh.

### Every `#[expect]` in the tree

| Where | Lints | Reason |
|---|---|---|
| `packages/rust/tests/contract/main.rs` (crate-level `#![expect]`) | `expect_used`, `unwrap_used`, `indexing_slicing`, `print_stderr` | test code: a failed expectation is a test failure; `print_stderr` reports a skipped root-only case |

| `packages/rust/src/check.rs`, `jcs.rs`, `formats.rs` (`#[cfg(test)]` modules) | `expect_used`, `indexing_slicing` | tests: a bad fixture is a test failure |
| `packages/rust/src/jcs.rs` (SHA-256 compression) | `many_single_char_names` | FIPS 180-4 names the working variables a..h |
| `packages/rust/src/formats.rs` (RFC 3339) | `many_single_char_names` | the RFC 3339 field names |

`src/` has no `#[allow]`. Outside test modules, the only `#[expect]` is `many_single_char_names`.

## 6. Deviations

* **Port-specific behavior** is listed as D-xxx entries in CONTRACT.md §Divergences, with fixtures in `fixtures/divergences.json`.
* **Rust-only contract entries** are marked `- **Languages:** rust`, for example C-073.
* **Bugs found while pinning behavior** (B-xxx entries in CONTRACT.md §B) were fixed in separate commits.
