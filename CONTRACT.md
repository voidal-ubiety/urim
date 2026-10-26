# urim check: behavior contract

This is the living contract for every behavior of `urim check` and the three library ports (`packages/js`, `packages/python`, `packages/rust`). Each entry has a stable ID. Every ID has at least one test in **each** language whose name contains the ID, and `scripts/contract-check.py` fails if an ID is missing anywhere. Change behavior only by changing this file, the fixtures and the tests together.

**Conventions.** `<file>` is the path exactly as passed. Result lines go to stdout (ok) or stderr (error), each followed by `\n`. Spec references are to [`spec/SPEC.md`](spec/SPEC.md) (DCTP v0.1.1 draft). "Implementation assumption" means the spec says nothing and v0.0.1 chose this. Checks run in the order of the sections below; the first failure wins.

**Test mapping.** File-level IDs are data-driven from [`fixtures/cases.json`](fixtures/cases.json) (each case has an `id`). CLI IDs come from [`fixtures/cli.json`](fixtures/cli.json), run with cwd `fixtures/`. In each language one test per ID runs that ID's cases:

| | file cases (`cases.json`) | CLI cases (`cli.json`) |
|---|---|---|
| JS (`node --test`) | `test/contract.test.mjs` › `C-0xx shared file cases (n)` | `test/cli.test.mjs` › `C-0xx shared CLI cases (n)` |
| Python (pytest) | `tests/test_contract.py::test_shared_file_cases[C-0xx]` | `tests/test_cli.py::test_shared_cli_cases[C-0xx]` |
| Rust (`cargo test`) | `tests/contract.rs::c0xx_…` | `tests/cli.rs::c0xx_…` |

`C-000` tests in every language check that each case is tagged and that the Rust per-ID test list equals the set of IDs in the JSON. `scripts/parity.sh` also runs every `cases.json` and `cli.json` case through all three CLIs and requires byte-identical results.

## 1. Command line

### C-001 Version flag

- **Behavior:** `urim --version` or `urim -V` (exactly one argument) → stdout `urim <VERSION>\n`, stderr empty, exit 0.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 2 case(s) in `cli.json`
- **Tests:** JS `C-001 shared CLI cases` · Python `test_shared_cli_cases[C-001]` · Rust `cli.rs::c001_version`

### C-002 Help flag

- **Behavior:** `urim --help` or `urim -h` (exactly one argument) → stdout `usage: urim check <file>\n`, exit 0.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 2 case(s) in `cli.json`
- **Tests:** JS `C-002 shared CLI cases` · Python `test_shared_cli_cases[C-002]` · Rust `cli.rs::c002_help`

### C-003 Usage error

- **Behavior:** Any other argv: no args, `check` without a file, `check a b`, an unknown subcommand, a flag with extra args, unknown/case-variant flags (`-v`, `--VERSION`, `CHECK`), a bare path → stderr `usage: urim check <file>\n`, stdout empty, exit 2. Nothing is read.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 11 case(s) in `cli.json`
- **Tests:** JS `C-003 shared CLI cases` · Python `test_shared_cli_cases[C-003]` · Rust `cli.rs::c003_usage_error`

### C-004 Valid file → stdout, exit 0

- **Behavior:** `urim check <file>` on a valid file prints the result line plus `\n` on stdout only; exit 0.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 1 case(s) in `cli.json`
- **Tests:** JS `C-004 shared CLI cases` · Python `test_shared_cli_cases[C-004]` · Rust `cli.rs::c004_ok_to_stdout`

### C-005 Invalid file → stderr, exit 1

- **Behavior:** `urim check <file>` on any failure prints the result line plus `\n` on stderr only; exit 1.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 2 case(s) in `cli.json`
- **Tests:** JS `C-005 shared CLI cases` · Python `test_shared_cli_cases[C-005]` · Rust `cli.rs::c005_error_to_stderr`

### C-006 Path echoed verbatim

- **Behavior:** The `<file>` in the message is the argument exactly as given (relative, `./`, `..`, doubled `/`, spaces, even `--version` as a file name). It is never resolved or canonicalized, so messages reveal nothing beyond what the caller passed.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 4 case(s) in `cli.json`
- **Tests:** JS `C-006 shared CLI cases` · Python `test_shared_cli_cases[C-006]` · Rust `cli.rs::c006_path_verbatim`

### C-007 Entry points

- **Behavior:** The command is named `urim`: npm `bin.urim` → `dist/cli.js` (node shebang); Python console script `urim = urim.cli:main`, plus `python -m urim` and `python -m urim.cli`; Rust `[[bin]] name = "urim"`.
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `cli.test.mjs` › `C-007 package bin entry point is dist/cli.js with a node shebang` · Python `test_cli.py::test_c007_module_entry_points`, `::test_c007_python_dash_m_subprocess`, `::test_c007_console_script_is_declared` · Rust `cli.rs::c007_binary_is_named_urim`

## 2. Reading the file

### C-010 Missing file

- **Behavior:** Nonexistent path → `<file>: error: cannot read file`, exit 1.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `invalid/does-not-exist.yaml`
- **Tests:** JS `C-001 shared file cases` · Python `test_shared_file_cases[C-010]` · Rust `contract.rs::c010_missing_file`

### C-011 Directory

- **Behavior:** A directory path → `<file>: error: cannot read file`, exit 1.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `valid`
- **Tests:** JS `C-011 shared file cases` · Python `test_shared_file_cases[C-011]` · Rust `contract.rs::c011_directory`

### C-012 Unreadable file

- **Behavior:** Permission denied → `<file>: error: cannot read file`, exit 1. The test creates a mode-000 file at runtime and skips when run as root (root bypasses permissions).
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `cli.test.mjs` › `C-012 unreadable file (permission denied) reports cannot read file` · Python `test_cli.py::test_c012_unreadable_file` · Rust `cli.rs::c012_permission_denied_is_cannot_read`

### C-013 Strict UTF-8

- **Behavior:** Bytes that are not valid UTF-8 (Latin-1, UTF-16 with BOM, CESU-encoded surrogates) → `<file>: error: file is not valid UTF-8`.
- **Spec:** §5.1 says contracts are YAML; strict UTF-8 is an implementation assumption.
- **Fixtures (3):** `invalid/encoded-surrogate.lock`, `invalid/not-utf8.yaml`, `invalid/utf16.lock`
- **Tests:** JS `C-012 shared file cases` · Python `test_shared_file_cases[C-013]` · Rust `contract.rs::c013_not_utf8`

### C-014 Leading BOM

- **Behavior:** One leading U+FEFF is ignored. A file that is only a BOM is empty, so it's null → `root must be a mapping`. (Double BOM: see D-007.)
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `invalid/bom-only.yaml`, `valid/bom.lock`
- **Tests:** JS `C-014 shared file cases` · Python `test_shared_file_cases[C-014]` · Rust `contract.rs::c014_bom`

### C-015 CRLF line endings

- **Behavior:** CRLF files parse the same as LF.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `valid/crlf.lock`
- **Tests:** JS `C-015 shared file cases` · Python `test_shared_file_cases[C-015]` · Rust `contract.rs::c015_crlf`

## 3. Parsing YAML (any failure → `<file>: error: invalid YAML`)

### C-020 Syntax errors

- **Behavior:** Malformed YAML (unclosed flow, tab indentation, bad indentation) → `invalid YAML`. Parser details are left out so messages match across languages.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `invalid/syntax-error.yaml`, `invalid/tab-indent.yaml`
- **Tests:** JS `C-020 shared file cases` · Python `test_shared_file_cases[C-020]` · Rust `contract.rs::c020_syntax_error`

### C-021 Duplicate keys

- **Behavior:** Duplicate mapping keys at any depth → `invalid YAML`, including keys that resolve to the same value (`~`/`null`, `0x1`/`1`).
- **Spec:** §5.3 ("YAML 1.2 core schema"); rejecting duplicates is an implementation assumption.
- **Fixtures (3):** `invalid/duplicate-hex-decimal-key.yaml`, `invalid/duplicate-key.yaml`, `invalid/duplicate-null-key.yaml`
- **Tests:** JS `C-021 shared file cases` · Python `test_shared_file_cases[C-021]` · Rust `contract.rs::c021_duplicate_keys`

### C-022 Exactly one document

- **Behavior:** More than one document (including a trailing `---` that opens an empty second document) → `invalid YAML`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `invalid/multi-document.yaml`, `invalid/trailing-empty-document.lock`
- **Tests:** JS `C-022 shared file cases` · Python `test_shared_file_cases[C-022]` · Rust `contract.rs::c022_single_document`

### C-023 Scalar keys only

- **Behavior:** A sequence or mapping used as a mapping key, at any depth, → `invalid YAML`. JS and Python cannot represent these faithfully. (Rust bug B-2 is fixed in its own commit.)
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `invalid/collection-key.lock`, `invalid/nested-collection-key.lock`, `invalid/tagged-key-with-collection-key.yaml`
- **Tests:** JS `C-023 shared file cases` · Python `test_shared_file_cases[C-023]` · Rust `contract.rs::c023_collection_keys`

### C-024 64-bit integers

- **Behavior:** Every integer in the document must be in −2^63..2^64−1. Anything outside that range anywhere → `invalid YAML`. The bounds themselves parse (`hoshen: 18446744073709551615` → `unsupported hoshen version 18446744073709551615 (supported: 1)`).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (6):** `invalid/hex-out-of-range.lock`, `invalid/hoshen-i64-min.lock`, `invalid/hoshen-u64-max.lock`, `invalid/int-below-i64-min.lock`, `invalid/int-out-of-range-elsewhere.lock`, `invalid/int-out-of-range.lock`
- **Tests:** JS `C-024 shared file cases` · Python `test_shared_file_cases[C-024]` · Rust `contract.rs::c024_int_range`

### C-025 Core-schema strings

- **Behavior:** YAML 1.2 core schema: `yes`/`no`/`on`/`off` and timestamps (`2026-10-25`) are strings; `true`/`True`/`TRUE` are booleans (so `urim: True` → `urim must be a string`). A `%YAML 1.1` directive does not switch to 1.1 booleans.
- **Spec:** §5.3 ("Contract parsers MUST use YAML 1.2 core schema").
- **Fixtures (4):** `invalid/lock-urim-true.lock`, `valid/urim-timestamp-is-a-string.lock`, `valid/urim-yes-is-a-string.decision.yaml`, `valid/yaml-1.1-directive-keeps-core-schema.lock`
- **Tests:** JS `C-025 shared file cases` · Python `test_shared_file_cases[C-025]` · Rust `contract.rs::c025_core_schema_strings`

### C-026 Integer forms

- **Behavior:** `0x` hex, `0o` octal and a `+` sign are integers (`hoshen: 0x1` is hoshen 1).
- **Spec:** §5.3 (core schema).
- **Fixtures (3):** `valid/hoshen-hex.lock`, `valid/hoshen-octal.lock`, `valid/hoshen-plus-sign.lock`
- **Tests:** JS `C-026 shared file cases` · Python `test_shared_file_cases[C-026]` · Rust `contract.rs::c026_int_forms`

### C-027 Non-integer lookalikes

- **Behavior:** Decimal with leading zeros (`01`), `0X1`, and `1_0` stay strings, so `hoshen: 01` → `hoshen must be an integer`. Leading zeros are an implementation assumption that matches serde_norway.
- **Spec:** §5.3 (core schema) plus implementation assumption.
- **Fixtures (3):** `invalid/hoshen-leading-zero.lock`, `invalid/hoshen-underscore.lock`, `invalid/hoshen-uppercase-hex-prefix.lock`
- **Tests:** JS `C-027 shared file cases` · Python `test_shared_file_cases[C-027]` · Rust `contract.rs::c027_non_int_forms`

### C-028 Floats are not integers

- **Behavior:** `1.0`, `1e0`, `.inf` are floats, so `hoshen` → `hoshen must be an integer`.
- **Spec:** §6.2 ("Integer format version").
- **Fixtures (3):** `invalid/hoshen-exponent.lock`, `invalid/hoshen-float.lock`, `invalid/hoshen-inf.lock`
- **Tests:** JS `C-028 shared file cases` · Python `test_shared_file_cases[C-028]` · Rust `contract.rs::c028_floats`

### C-029 Explicit core tags

- **Behavior:** `!!str 1` is a string, `!!int "1"` is an integer, `!!float 1` is a float.
- **Spec:** §5.3 (core schema).
- **Fixtures (3):** `invalid/hoshen-tagged-float.lock`, `invalid/hoshen-tagged-str.lock`, `valid/hoshen-tagged-int-string.lock`
- **Tests:** JS `C-029 shared file cases` · Python `test_shared_file_cases[C-029]` · Rust `contract.rs::c029_explicit_tags`

### C-030 Empty document is null

- **Behavior:** An empty file, a comments-only file, and a bare `---` are null → `root must be a mapping`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `invalid/comments-only.yaml`, `invalid/empty.yaml`, `invalid/explicit-empty-document.yaml`
- **Tests:** JS `C-030 shared file cases` · Python `test_shared_file_cases[C-030]` · Rust `contract.rs::c030_null_root`

### C-031 Root must be a mapping

- **Behavior:** A root that is a scalar or sequence → `<file>: error: root must be a mapping`. A flow mapping root is fine.
- **Spec:** §5.1 / §6.2 (top-level keys).
- **Fixtures (3):** `invalid/root-scalar.yaml`, `invalid/root-sequence.yaml`, `valid/flow-mapping-root.lock`
- **Tests:** JS `C-031 shared file cases` · Python `test_shared_file_cases[C-031]` · Rust `contract.rs::c031_non_mapping_root`

### C-032 Anchors and aliases

- **Behavior:** Anchors and aliases resolve normally (an aliased `urim` string works).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `valid/anchor-alias.lock`
- **Tests:** JS `C-032 shared file cases` · Python `test_shared_file_cases[C-032]` · Rust `contract.rs::c032_anchors_aliases`

### C-033 No merge keys

- **Behavior:** `<<` is an ordinary key; it is not merged.
- **Spec:** §5.3 (YAML 1.2 core has no merge keys).
- **Fixtures (1):** `invalid/merge-key-not-applied.yaml`
- **Tests:** JS `C-033 shared file cases` · Python `test_shared_file_cases[C-033]` · Rust `contract.rs::c033_no_merge_keys`

### C-034 Exact key spelling

- **Behavior:** Keys match exactly: `Hoshen`, `"hoshen "` and a quoted `"hoshen"` are compared as strings; integer key `1` differs from string key `"1"`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `valid/key-spellings.lock`, `valid/string-and-int-keys-distinct.lock`
- **Tests:** JS `C-034 shared file cases` · Python `test_shared_file_cases[C-034]` · Rust `contract.rs::c034_key_spelling`

### C-035 Keys of different types are distinct

- **Behavior:** Key equality includes the YAML type: `true` and `1`, or `1` and `1.0`, in the same mapping are distinct keys, not duplicates.
- **Spec:** §5.3 ("YAML 1.2 core schema"; under YAML 1.2, node equality includes the tag). Which keys count as duplicates is an implementation assumption, extending C-021. Added for bug B-1.
- **Fixtures (2):** `valid/bool-and-int-keys-distinct.lock`, `valid/int-and-float-keys-distinct.lock`
- **Tests:** JS `C-035 shared file cases` · Python `test_shared_file_cases[C-035]` · Rust `contract.rs::c035_keys_distinct_by_type`

## 4. Lockfile (root has `hoshen`)

### C-040 hoshen wins

- **Behavior:** If `hoshen` is present the file is a lockfile, even if `dctp`/`urim` contract keys are also present.
- **Spec:** §6.2 ("MUST read `hoshen` before anything else").
- **Fixtures (2):** `invalid/lockfile-dctp-is-not-urim.lock`, `valid/lockfile-wins-over-dctp.lock`
- **Tests:** JS `C-040 shared file cases` · Python `test_shared_file_cases[C-040]` · Rust `contract.rs::c040_hoshen_precedence`

### C-041 hoshen must be an integer

- **Behavior:** Strings, booleans, null, an empty value, sequences and mappings → `<file>: error: hoshen must be an integer`.
- **Spec:** §6.2 ("Integer format version").
- **Fixtures (6):** `invalid/hoshen-bool.lock`, `invalid/hoshen-empty-value.lock`, `invalid/hoshen-mapping.lock`, `invalid/hoshen-null.lock`, `invalid/hoshen-sequence.lock`, `invalid/hoshen-string.lock`
- **Tests:** JS `C-041 shared file cases` · Python `test_shared_file_cases[C-041]` · Rust `contract.rs::c041_hoshen_not_int`

### C-042 Unsupported hoshen

- **Behavior:** An integer outside the supported set → `<file>: error: unsupported hoshen version N (supported: 1)`, with N in decimal (`0x2` → `2`, `-0` → `0`). This names both versions.
- **Spec:** §6.2 ("MUST refuse, with an error naming both versions").
- **Fixtures (5):** `invalid/hoshen-negative-zero.lock`, `invalid/hoshen-negative.lock`, `invalid/hoshen-unsupported-hex.lock`, `invalid/hoshen-unsupported.lock`, `invalid/hoshen-zero.lock`
- **Tests:** JS `C-042 shared file cases` · Python `test_shared_file_cases[C-042]` · Rust `contract.rs::c042_hoshen_unsupported`

### C-043 urim required

- **Behavior:** No `urim` key → `<file>: error: missing required key(s): urim`.
- **Spec:** §6.2 (top-level `urim`).
- **Fixtures (1):** `invalid/lock-missing-urim.lock`
- **Tests:** JS `C-043 shared file cases` · Python `test_shared_file_cases[C-043]` · Rust `contract.rs::c043_urim_missing`

### C-044 urim must be a string

- **Behavior:** Integer, float, null or mapping `urim` → `<file>: error: urim must be a string`. YAML `0.1` unquoted is a float, so it's rejected.
- **Spec:** §6.2 (`urim` is `"0.1"`, a string).
- **Fixtures (4):** `invalid/lock-urim-int.lock`, `invalid/lock-urim-mapping.lock`, `invalid/lock-urim-not-string.lock`, `invalid/lock-urim-null.lock`
- **Tests:** JS `C-044 shared file cases` · Python `test_shared_file_cases[C-044]` · Rust `contract.rs::c044_urim_not_string`

### C-045 Lockfile ok

- **Behavior:** → stdout `<file>: ok (lockfile, hoshen N, urim V)`, exit 0. V is printed verbatim (an empty string is allowed). Other fields (`generated_at`, `compiler`, `contracts`) are not checked in v0.0.1.
- **Spec:** §6.2.
- **Fixtures (3):** `../spec/examples/urim.lock`, `valid/lock-urim-empty-string.lock`, `valid/minimal.lock`
- **Tests:** JS `C-045 shared file cases` · Python `test_shared_file_cases[C-045]` · Rust `contract.rs::c045_lockfile_ok`

### C-046 Lockfile check order

- **Behavior:** hoshen type → hoshen supported → urim present → urim type; the first failure wins.
- **Spec:** §6.2 (hoshen first); the rest of the order is an implementation assumption.
- **Fixtures (2):** `invalid/lock-order-hoshen-type-first.lock`, `invalid/lock-order-version-before-urim.lock`
- **Tests:** JS `C-046 shared file cases` · Python `test_shared_file_cases[C-046]` · Rust `contract.rs::c046_lockfile_order`

## 5. Contract (root has `dctp` or `urim`, no `hoshen`)

### C-050 Only one version key

- **Behavior:** Both `dctp` and `urim` → `<file>: error: set only one of 'dctp' or 'urim'`, checked before their types.
- **Spec:** §5.1 names `dctp`; accepting `urim` as an alias is an implementation assumption.
- **Fixtures (2):** `invalid/contract-both-keys-bad-types.decision.yaml`, `invalid/contract-both-version-keys.decision.yaml`
- **Tests:** JS `C-050 shared file cases` · Python `test_shared_file_cases[C-050]` · Rust `contract.rs::c050_contract_both_keys`

### C-051 Version key is a string

- **Behavior:** `<file>: error: dctp must be a string` (or `urim must be a string`).
- **Spec:** §5.1 (`dctp: "0.1"`).
- **Fixtures (3):** `invalid/contract-dctp-not-string.decision.yaml`, `invalid/contract-dctp-null.decision.yaml`, `invalid/contract-urim-not-string.decision.yaml`
- **Tests:** JS `C-051 shared file cases` · Python `test_shared_file_cases[C-051]` · Rust `contract.rs::c051_contract_key_type`

### C-052 Required keys

- **Behavior:** Any of `contract`, `version`, `state`, `questions` missing → `<file>: error: missing required key(s): a, b`, listing all missing keys in that order.
- **Spec:** §5.1 (REQUIRED keys).
- **Fixtures (3):** `invalid/contract-missing-all.decision.yaml`, `invalid/contract-missing-keys.decision.yaml`, `invalid/contract-missing-state-only.decision.yaml`
- **Tests:** JS `C-052 shared file cases` · Python `test_shared_file_cases[C-052]` · Rust `contract.rs::c052_contract_missing_keys`

### C-053 contract and version are strings

- **Behavior:** → `contract must be a string`, then `version must be a string` (contract is checked first). Kebab-case and semver formats are not checked.
- **Spec:** §5.1 / §6.1.
- **Fixtures (3):** `invalid/contract-id-checked-before-version.decision.yaml`, `invalid/contract-id-not-string.decision.yaml`, `invalid/contract-version-not-string.decision.yaml`
- **Tests:** JS `C-053 shared file cases` · Python `test_shared_file_cases[C-053]` · Rust `contract.rs::c053_contract_string_fields`

### C-054 state is a mapping

- **Behavior:** Anything that isn't a mapping → `<file>: error: state must be a mapping`. An empty mapping is fine.
- **Spec:** §5.2.
- **Fixtures (3):** `invalid/contract-state-not-mapping.decision.yaml`, `invalid/contract-state-null.decision.yaml`, `valid/contract-empty-state.decision.yaml`
- **Tests:** JS `C-054 shared file cases` · Python `test_shared_file_cases[C-054]` · Rust `contract.rs::c054_contract_state`

### C-055 questions is a non-empty mapping

- **Behavior:** → `<file>: error: questions must be a non-empty mapping`.
- **Spec:** §5.1 ("ordered map, >= 1") / §5.3.
- **Fixtures (3):** `invalid/contract-empty-questions.decision.yaml`, `invalid/contract-questions-null.decision.yaml`, `invalid/contract-questions-sequence.decision.yaml`
- **Tests:** JS `C-055 shared file cases` · Python `test_shared_file_cases[C-055]` · Rust `contract.rs::c055_contract_questions`

### C-056 Contract ok

- **Behavior:** → stdout `<file>: ok (contract ID@VERSION, KEY V)`, exit 0, values printed verbatim (multi-line strings included).
- **Spec:** §5.1.
- **Fixtures (4):** `../spec/examples/incident-triage.decision.yaml`, `../spec/examples/kyc-document-check.decision.yaml`, `valid/contract-multiline-id.decision.yaml`, `valid/minimal-urim.decision.yaml`
- **Tests:** JS `C-056 shared file cases` · Python `test_shared_file_cases[C-056]` · Rust `contract.rs::c056_contract_ok`

### C-057 Contract check order

- **Behavior:** both keys → key type → missing keys → contract type → version type → state → questions.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `invalid/contract-order-key-type-first.decision.yaml`, `invalid/contract-order-missing-before-types.decision.yaml`, `invalid/contract-order-state-before-questions.decision.yaml`
- **Tests:** JS `C-057 shared file cases` · Python `test_shared_file_cases[C-057]` · Rust `contract.rs::c057_contract_order`

## 6. Everything else

### C-060 Not a urim document

- **Behavior:** A mapping with none of `hoshen`/`dctp`/`urim` (including `{}` and provider descriptors) → `<file>: error: not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `../spec/examples/providers/cloudflare-clef-flash.provider.yaml`, `invalid/empty-mapping.yaml`, `invalid/unrecognized.yaml`
- **Tests:** JS `C-060 shared file cases` · Python `test_shared_file_cases[C-060]` · Rust `contract.rs::c060_not_urim`

## 7. Library API

### C-070 checkText / check_text

- **Behavior:** Validates text in memory. The file argument is used only in the message, and one leading BOM is stripped.
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `api.test.mjs` › `C-070 …` · Python `test_api.py::test_c070_check_text_uses_file_only_in_the_message` · Rust `api.rs::c070_check_text_uses_file_only_in_message`

### C-071 Result shape

- **Behavior:** JS `{ok, line, exitCode}`; Python `CheckResult(ok, line)` with `.exit_code`; Rust `CheckResult { ok, line }` with `exit_code()`. Exit code is 0 iff ok, else 1.
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `api.test.mjs` › `C-071 …` · Python `test_api.py::test_c071_result_carries_ok_line_and_exit_code` · Rust `api.rs::c071_result_fields_and_exit_code`

### C-072 Constants

- **Behavior:** `SUPPORTED_HOSHEN` = {1} (JS `[1n]` bigint array, Python `frozenset({1})`, Rust `&[1]`). `VERSION` equals the package manifest version.
- **Spec:** §6.2 ("currently `1`").
- **Tests:** JS `api.test.mjs` › `C-072 …` · Python `test_api.py::test_c072_supported_hoshen_and_version` · Rust `api.rs::c072_supported_hoshen_and_version`

## D. Known cross-language divergences (outside the conformance set)

These inputs behave differently across the three ports because the underlying YAML libraries differ. Every port **pins its own current behavior** from [`fixtures/divergences.json`](fixtures/divergences.json), so any change is deliberate. `parity.sh` skips them. Resolving each one is a behavior change for David to decide; a recommendation is given for each.

Tests: JS `test/divergences.test.mjs` › `D-0xx pinned JS behavior` · Python `tests/test_divergences.py::test_pinned_python_behavior[D-0xx]` · Rust `tests/divergences.rs::d000_divergences_pin_rust_behavior` (all D cases).

### D-001 Unknown local tag on a scalar (`hoshen: !foo 1`)

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/custom-tag-scalar.lock` | exit 1: `error: hoshen must be an integer` | exit 1: `error: invalid YAML` | exit 1: `error: hoshen must be an integer` |

- **Why:** Rust and JS ignore the unknown tag and see the scalar; PyYAML has no constructor for it.
- **Recommendation:** Treat unknown local tags as untagged everywhere, or reject them everywhere (Python's behavior is the stricter one).

### D-002 `!!int` on a non-numeric scalar (`!!int abc`)

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/int-tag-non-numeric.lock` | exit 1: `error: hoshen must be an integer` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |

- **Why:** JS's yaml keeps it as an int-tagged value that fails the integer check; PyYAML and serde_norway fail to resolve it.
- **Recommendation:** Reject as `invalid YAML` everywhere (2 of 3).

### D-003 `!!timestamp` / `!!binary` on `urim`

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/timestamp-tag.lock` | exit 1: `error: urim must be a string` | exit 1: `error: urim must be a string` | exit 0: `ok (lockfile, hoshen 1, urim 2026-01-01)` |
| `divergent/binary-tag.lock` | exit 1: `error: urim must be a string` | exit 1: `error: urim must be a string` | exit 0: `ok (lockfile, hoshen 1, urim aGk=)` |

- **Why:** These tags aren't in the core schema. JS and Python construct non-string values; serde_norway's `Value` yields a string.
- **Recommendation:** Reject as `urim must be a string` (2 of 3), or make all three ignore non-core tags.

### D-004 Local tag on a mapping root (`!t {...}`)

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/custom-tag-mapping.lock` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 1: `error: invalid YAML` | exit 0: `ok (lockfile, hoshen 1, urim x)` |

- **Why:** JS and Rust see through the tag; PyYAML can't construct it.
- **Recommendation:** Same decision as D-001.

### D-005 C0 control characters / NUL in the text

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/control-char.lock` | exit 0: `ok (lockfile, hoshen 1, urim a)` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |
| `divergent/nul-byte.lock` | exit 0: `ok (lockfile, hoshen 1, urim x )` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |

- **Why:** YAML forbids them in a stream. PyYAML and libyaml reject them; JS's yaml accepts them.
- **Recommendation:** Reject everywhere with `invalid YAML` (2 of 3, and what YAML 1.2 §5.1 says).

### D-006 NEL (U+0085) in the text

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/next-line-char.lock` | exit 0: `ok (lockfile, hoshen 1, urim ab)` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |

- **Why:** PyYAML and libyaml reject it here; JS's yaml accepts it.
- **Recommendation:** Follow D-005's resolution.

### D-007 Two leading BOMs

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/double-bom.lock` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 1: `error: invalid YAML` |

- **Why:** Rust strips one BOM and libyaml rejects the second; JS and Python tolerate it.
- **Recommendation:** Strip exactly one BOM and reject a second one everywhere, or strip both everywhere.

### D-008 A stream that is only `...`

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/document-end-only.yaml` | exit 1: `error: root must be a mapping` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |

- **Why:** JS reads it as an empty document (null root); PyYAML and libyaml reject the stray document-end marker.
- **Recommendation:** Reject as `invalid YAML` (2 of 3).

### D-009 `%YAML 1.3` / unknown `%` directives

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/yaml-1.3-directive.lock` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 1: `error: invalid YAML` |
| `divergent/unknown-directive.lock` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 1: `error: invalid YAML` |

- **Why:** libyaml rejects them; JS's yaml and PyYAML accept the document.
- **Recommendation:** Accept with a 1.2 reading everywhere, or reject everywhere. Low priority.

### D-010 Alias expansion over 100 nodes

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/alias-expansion-over-100.lock` | exit 1: `error: invalid YAML` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 0: `ok (lockfile, hoshen 1, urim x)` |

- **Why:** JS's yaml capped expansion at maxAliasCount 100; PyYAML shares nodes and serde_norway allowed it.
- **Recommendation:** Superseded by the shared hostile-input limits (C-082) once they land.

### D-011 Duplicate `.nan` keys

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/duplicate-nan-key.lock` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |

- **Why:** NaN ≠ NaN, so JS's uniqueness check passes them; PyYAML and serde_norway treat the two `.nan` keys as duplicates.
- **Recommendation:** Reject as duplicates (2 of 3, matching YAML's node-equality rule).

## B. Bugs found by this suite

Each fix is its own commit, with the fixture failing before the fix and passing after it.

- **B-1 (Python): keys of different types compared equal.** `{true: a, 1: b}` and `{1: a, 1.0: b}` were rejected as duplicate keys (→ `invalid YAML`) because Python's `True == 1 == 1.0`. YAML node equality includes the tag, and JS and Rust accept both. Pinned as **C-035**; fixed in `src/urim/check.py` by comparing keys as `(type, value)`. Separate commit, failing then passing.
- **B-2 (Rust): a collection key under a local tag was accepted.** `? !t [1]` as a key passed in Rust, against C-023; JS and Python reject it. Pinned as a C-023 fixture.

## X. Coverage exclusions

No coverage-exclusion pragmas are used in any language. Code that coverage showed to be unreachable was deleted in the refactor commit, not excluded. Any future pragma must be listed here with its reason.
