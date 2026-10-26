# urim check: behavior contract

This is the living contract for every behavior of `urim check` and the three library ports (`packages/js`, `packages/python`, `packages/rust`). Each entry has a stable ID. Every ID has at least one test in **each** language whose name contains the ID, and `scripts/contract-check.py` fails if an ID is missing anywhere. Change behavior only by changing this file, the fixtures and the tests together.

**Conventions.** `<file>` is the path exactly as passed. Result lines go to stdout (ok) or stderr (error), each followed by `\n`. Spec references are to [`spec/SPEC.md`](spec/SPEC.md) (DCTP v0.1.1 draft). "Implementation assumption" means the spec says nothing and v0.0.1 chose this. Checks run in the order of the sections below, except that the profile rules in §3 interleave with YAML syntax errors in stream order (C-090). The first failure wins.

**Retired and resolved IDs.** An ID is never reused. When a rule is replaced its section stays as a stub with a `- **Status:**` line naming what replaced it. `contract-check.py` requires that no test or fixture still uses a retired or resolved ID, and that every `**Fixtures (n):**` list matches `fixtures/cases.json` exactly. "v0.0.2" names the next, unreleased checker version: the packages are still at 0.0.1 and nothing has been published.

**Test mapping.** File-level IDs are data-driven from [`fixtures/cases.json`](fixtures/cases.json) (each case has an `id`). CLI IDs come from [`fixtures/cli.json`](fixtures/cli.json), run with cwd `fixtures/`. In each language one test per ID runs that ID's cases:

| | file cases (`cases.json`) | CLI cases (`cli.json`) |
|---|---|---|
| JS (`node --test`) | `test/contract.test.mjs` › `C-0xx shared file cases (n)` | `test/cli.test.mjs` › `C-0xx shared CLI cases (n)` |
| Python (pytest) | `tests/test_contract.py::test_shared_file_cases[C-0xx]` | `tests/test_cli.py::test_shared_cli_cases[C-0xx]` |
| Rust (`cargo test`) | `tests/contract/files.rs::c0xx_…` | `tests/contract/cli.rs::c0xx_…` |

`C-000` tests in every language check that each case is tagged and that the Rust per-ID test list equals the set of IDs in the JSON. `scripts/parity.sh` also runs every `cases.json` and `cli.json` case through all three CLIs and requires byte-identical results.

## 1. Command line

### C-001 Version flag

- **Behavior:** `urim --version` or `urim -V` (exactly one argument) → stdout `urim <VERSION>\n`, stderr empty, exit 0.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 2 case(s) in `cli.json`
- **Tests:** JS `C-001 shared CLI cases` · Python `test_shared_cli_cases[C-001]` · Rust `contract/cli.rs::c001_version`

### C-002 Help flag

- **Behavior:** `urim --help` or `urim -h` (exactly one argument) → stdout `usage: urim check <file>\n`, exit 0.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 2 case(s) in `cli.json`
- **Tests:** JS `C-002 shared CLI cases` · Python `test_shared_cli_cases[C-002]` · Rust `contract/cli.rs::c002_help`

### C-003 Usage error

- **Behavior:** Any other argv: no args, `check` without a file, `check a b`, an unknown subcommand, a flag with extra args, unknown/case-variant flags (`-v`, `--VERSION`, `CHECK`), a bare path → stderr `usage: urim check <file>\n`, stdout empty, exit 2. Nothing is read.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 11 case(s) in `cli.json`
- **Tests:** JS `C-003 shared CLI cases` · Python `test_shared_cli_cases[C-003]` · Rust `contract/cli.rs::c003_usage_error`

### C-004 Valid file → stdout, exit 0

- **Behavior:** `urim check <file>` on a valid file prints the result line plus `\n` on stdout only; exit 0.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 1 case(s) in `cli.json`
- **Tests:** JS `C-004 shared CLI cases` · Python `test_shared_cli_cases[C-004]` · Rust `contract/cli.rs::c004_ok_to_stdout`

### C-005 Invalid file → stderr, exit 1

- **Behavior:** `urim check <file>` on any failure prints the result line plus `\n` on stderr only; exit 1.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 2 case(s) in `cli.json`
- **Tests:** JS `C-005 shared CLI cases` · Python `test_shared_cli_cases[C-005]` · Rust `contract/cli.rs::c005_error_to_stderr`

### C-006 Path echoed verbatim

- **Behavior:** The `<file>` in the message is the argument exactly as given (relative, `./`, `..`, doubled `/`, spaces, even `--version` as a file name). It is never resolved or canonicalized, so messages reveal nothing beyond what the caller passed.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures:** 4 case(s) in `cli.json`
- **Tests:** JS `C-006 shared CLI cases` · Python `test_shared_cli_cases[C-006]` · Rust `contract/cli.rs::c006_path_verbatim`

### C-007 Entry points

- **Behavior:** The command is named `urim`: npm `bin.urim` → `dist/cli.js` (node shebang); Python console script `urim = urim.cli:main`, plus `python -m urim` and `python -m urim.cli`; Rust `[[bin]] name = "urim"`.
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `cli.test.mjs` › `C-007 package bin entry point is dist/cli.js with a node shebang` · Python `test_cli.py::test_c007_module_entry_points`, `::test_c007_python_dash_m_subprocess`, `::test_c007_console_script_is_declared` · Rust `contract/cli.rs::c007_binary_is_named_urim`

## 2. Reading the file

### C-010 Missing file

- **Behavior:** Nonexistent path → `<file>: error: cannot read file`, exit 1.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `invalid/does-not-exist.yaml`
- **Tests:** JS `C-010 shared file cases` · Python `test_shared_file_cases[C-010]` · Rust `contract/files.rs::c010_missing_file`

### C-011 Directory

- **Behavior:** A directory path → `<file>: error: not a regular file`, exit 1 (C-081; before v0.0.2 this was `cannot read file`).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `valid`
- **Tests:** JS `C-011 shared file cases` · Python `test_shared_file_cases[C-011]` · Rust `contract/files.rs::c011_directory`

### C-012 Unreadable file

- **Behavior:** Permission denied → `<file>: error: cannot read file`, exit 1. The test creates a mode-000 file at runtime and skips when run as root (root bypasses permissions).
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `cli.test.mjs` › `C-012 unreadable file (permission denied) reports cannot read file` · Python `test_cli.py::test_c012_unreadable_file` · Rust `contract/cli.rs::c012_permission_denied_is_cannot_read`

### C-013 Strict UTF-8

- **Behavior:** Bytes that are not valid UTF-8 (Latin-1, UTF-16 with BOM, CESU-encoded surrogates) → `<file>: error: file is not valid UTF-8`. A read that fails after the file has opened (for example `EIO` from `/proc/self/mem`) → `<file>: error: cannot read file`.
- **Spec:** §5.1 says contracts are YAML; strict UTF-8 is an implementation assumption.
- **Fixtures (3):** `invalid/encoded-surrogate.lock`, `invalid/not-utf8.yaml`, `invalid/utf16.lock`
- **Tests:** JS `C-013 shared file cases`, `limits.test.mjs` › `C-013 a read error after a successful open …` · Python `test_shared_file_cases[C-013]`, `test_limits.py::test_c013_read_error_after_open_is_cannot_read` · Rust `contract/files.rs::c013_not_utf8`, `contract/limits.rs::c013_read_error_after_open_is_cannot_read`

### C-014 Leading BOM

- **Behavior:** One leading U+FEFF is ignored. A file that is only a BOM is empty, so it's null → `root must be a mapping`. A second U+FEFF anywhere, including right after the first, → `invalid YAML` (C-082).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `invalid/bom-only.yaml`, `valid/bom.lock`
- **Tests:** JS `C-014 shared file cases` · Python `test_shared_file_cases[C-014]` · Rust `contract/files.rs::c014_bom`

### C-015 CRLF line endings

- **Behavior:** CRLF files parse the same as LF.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (1):** `valid/crlf.lock`
- **Tests:** JS `C-015 shared file cases` · Python `test_shared_file_cases[C-015]` · Rust `contract/files.rs::c015_crlf`

### C-080 Size limit

- **Behavior:** Input larger than `MAX_BYTES` = 1 048 576 bytes (1 MiB, counted in UTF-8 bytes, before BOM stripping) → `<file>: error: file too large (max 1048576 bytes)`. A file of exactly `MAX_BYTES` is accepted. Files are read with a bound of `MAX_BYTES + 1` bytes, so a growing or `/proc` file cannot make the reader allocate without limit. `checkText` / `check_text` apply the same limit. `MAX_BYTES` and `MAX_DEPTH` are exported by every port.
- **Spec:** §5.1.1 (Urim YAML profile).
- **Tests:** JS `limits.test.mjs` › `C-080 …` · Python `test_limits.py::test_c080_limits_are_exported`, `::test_c080_exactly_max_bytes_is_accepted_one_more_is_too_large` · Rust `contract/limits.rs::c080_limits_are_exported`, `::c080_exactly_max_bytes_is_accepted_one_more_is_too_large`

### C-081 Regular files only

- **Behavior:** The path is opened non-blocking, and the *opened handle* is inspected, so there is no stat-then-open race. Anything that is not a regular file (directory, FIFO, socket, `/dev/zero`, `/dev/null`) → `<file>: error: not a regular file` without blocking or reading. A symlink to a regular file is followed.
- **Spec:** §5.1.1.
- **Tests:** JS `limits.test.mjs` › `C-081 …` · Python `test_limits.py::test_c081_fifos_and_devices_are_refused_symlinks_followed` · Rust `contract/limits.rs::c081_fifos_and_devices_are_refused_symlinks_followed`

## 3. The Urim YAML profile (strict subset of YAML 1.2)

Every port applies the same rules in the same order. Steps 1–3 run before any value is built.

1. **Characters** (C-082). One leading U+FEFF is stripped. After that, every character must be YAML 1.2 `c-printable` and must not be NEL, LS, PS or U+FEFF.
2. **Well-formedness, in stream order** (C-083, C-020, C-022). Nesting deeper than `MAX_DEPTH` is reported if it comes before the first syntax error, undefined alias or second document. Those are `invalid YAML`.
3. **Profile violations over the whole event stream, first one wins** (C-084..C-087). Anchor or alias, tag, `<<` key, invisible character in a key.
4. **Values** (§4): duplicate keys, collection keys and integer range; core-schema resolution.
5. **Schema** (§5–§7), where identifiers must not contain invisible characters (C-088).

Output is sanitized in every result line (C-089).

### C-082 Profile characters only

- **Behavior:** Any character outside YAML 1.2 `c-printable` anywhere in the text (C0 controls other than TAB/LF/CR, NUL, DEL, C1 controls, lone surrogates), or NEL (U+0085), LINE SEPARATOR (U+2028), PARAGRAPH SEPARATOR (U+2029), or U+FEFF other than one leading BOM, → `invalid YAML`. This applies even inside quoted scalars and comments. NEL, LS and PS are excluded because YAML 1.1 parsers treat them as line breaks and YAML 1.2 does not, so two parsers could read different structure from the same bytes. This is the C-082 extension that resolves D-005, D-006 and D-007.
- **Spec:** §5.1.1; YAML 1.2 §5.1 (`c-printable`).
- **Fixtures (7):** `invalid/bom-in-quoted-scalar.lock`, `invalid/bom-not-leading.lock`, `invalid/control-char.lock`, `invalid/line-separator.lock`, `invalid/next-line-char.lock`, `invalid/nul-byte.lock`, `invalid/paragraph-separator.lock`
- **Tests:** JS `C-082 shared file cases` · Python `test_shared_file_cases[C-082]` · Rust `contract/files.rs::c082_printable_only`

### C-083 Nesting depth limit

- **Behavior:** Collections nested deeper than `MAX_DEPTH` = 64 (the root mapping is depth 1) → `<file>: error: nesting too deep (max depth 64)`. Depth 64 is accepted. This holds for block and flow style, and for unclosed input such as 5 000 `[`. Each port's parser-level nesting error maps to the same message. No port recurses on input depth beyond this limit.
- **Spec:** §5.1.1.
- **Fixtures (4):** `invalid/depth-5000-unclosed.lock`, `invalid/depth-65-block.lock`, `invalid/depth-65.lock`, `valid/depth-64.lock`
- **Tests:** JS `C-083 shared file cases` · Python `test_shared_file_cases[C-083]` · Rust `contract/files.rs::c083_depth_limit`

### C-084 No anchors or aliases

- **Behavior:** Any anchor (`&a`, used or not, on a scalar or a collection) or alias (`*a`) → `<file>: error: anchors and aliases are not allowed`. This removes alias-expansion attacks (billion laughs) and resolves D-010.
- **Spec:** §5.1.1.
- **Fixtures (4):** `invalid/alias-expansion-over-100.lock`, `invalid/anchor-alias.lock`, `invalid/anchor-on-collection.lock`, `invalid/anchor-only.lock`
- **Tests:** JS `C-084 shared file cases` · Python `test_shared_file_cases[C-084]` · Rust `contract/files.rs::c084_no_anchors_aliases`

### C-085 No tags

- **Behavior:** Any tag on any node, including the root, keys, the non-specific `!` and core tags such as `!!str` and `!!int`, → `<file>: error: tags are not allowed`. Values are always resolved by the YAML 1.2 core schema from their plain or quoted form. This replaces C-029 and resolves D-001..D-004.
- **Spec:** §5.1.1.
- **Fixtures (13):** `invalid/hoshen-tagged-float.lock`, `invalid/hoshen-tagged-int-string.lock`, `invalid/hoshen-tagged-str.lock`, `invalid/tag-binary.lock`, `invalid/tag-core-str.lock`, `invalid/tag-custom-mapping.lock`, `invalid/tag-custom-scalar.lock`, `invalid/tag-int-non-numeric.lock`, `invalid/tag-non-specific.lock`, `invalid/tag-on-root.lock`, `invalid/tag-timestamp.lock`, `invalid/tagged-collection-key.yaml`, `invalid/tagged-key-with-collection-key.yaml`
- **Tests:** JS `C-085 shared file cases` · Python `test_shared_file_cases[C-085]` · Rust `contract/files.rs::c085_no_tags`

### C-086 No merge keys

- **Behavior:** A mapping key whose scalar value is `<<`, plain or quoted, → `<file>: error: merge keys (<<) are not allowed`. This replaces C-033.
- **Spec:** §5.1.1.
- **Fixtures (2):** `invalid/merge-key-not-applied.yaml`, `invalid/merge-key-quoted.lock`
- **Tests:** JS `C-086 shared file cases` · Python `test_shared_file_cases[C-086]` · Rust `contract/files.rs::c086_no_merge_keys`

### C-087 No invisible characters in keys

- **Behavior:** A mapping key at any depth containing an invisible or bidirectional-control character → `<file>: error: invisible or bidirectional control character in a mapping key`. The set is U+00AD, U+061C, U+180E, U+200B..U+200F, U+202A..U+202E, U+2060..U+2064, U+2066..U+206F, U+FEFF, U+FFF9..U+FFFB and U+E0000..U+E007F. It stops look-alike keys such as `urim\u{200B}` from shadowing real ones.
- **Spec:** §5.1.1.
- **Fixtures (3):** `invalid/invisible-bidi-key.lock`, `invalid/invisible-tag-char-key.lock`, `invalid/invisible-zwsp-key.lock`
- **Tests:** JS `C-087 shared file cases` · Python `test_shared_file_cases[C-087]` · Rust `contract/files.rs::c087_no_invisible_in_keys`

### C-088 No invisible characters in identifiers

- **Behavior:** If the string value of `urim`, `dctp`, `contract` or `version` contains a C-087 character → `<file>: error: invisible or bidirectional control character in <key>`. This check runs right after that key's "must be a string" check, in the existing schema order (C-046, C-057).
- **Spec:** §5.1.1.
- **Fixtures (4):** `invalid/invisible-in-contract.yaml`, `invalid/invisible-in-dctp.yaml`, `invalid/invisible-in-urim.lock`, `invalid/invisible-in-version.yaml`
- **Tests:** JS `C-088 shared file cases` · Python `test_shared_file_cases[C-088]` · Rust `contract/files.rs::c088_no_invisible_in_identifiers`

### C-089 Output is sanitized

- **Behavior:** In every result line, the file name and every echoed value (`urim`, `contract`, `version`, `dctp`) have C0 controls, DEL, C1 controls, lone surrogates and C-087 characters escaped as `\u{XXXX}` (uppercase hex, at least 4 digits). A backslash is not escaped, so `a\u{0041}b` in a file prints as typed. A file name that is not valid UTF-8 shows U+FFFD for each undecodable byte.
- **Spec:** §5.1.1.
- **Fixtures (3):** `valid/backslash-in-urim.lock`, `valid/escape-in-contract.yaml`, `valid/escape-in-urim.lock`
- **Tests:** JS `C-089 shared file cases`, `limits.test.mjs` › `C-089 …` · Python `test_shared_file_cases[C-089]`, `test_limits.py::test_c089_unsafe_characters_in_the_file_name_are_escaped` · Rust `contract/files.rs::c089_output_sanitized`, `contract/limits.rs::c089_unsafe_characters_in_the_file_name_are_escaped`

### C-090 First violation in stream order

- **Behavior:** Precedence follows the steps at the top of §3:
  - A non-profile character beats everything after it, including an earlier syntax error.
  - Depth beats a syntax error, undefined alias or second document only when the 65th open collection comes first in the stream, and it also beats an earlier profile violation.
  - Any syntax error, undefined alias or second document beats every profile violation, even an earlier one.
  - Among profile violations the first in the stream wins. On one node an anchor beats a tag.
  - Every profile violation beats every value error (duplicate key, collection key) and every schema error.
- **Spec:** §5.1.1.
- **Same flow line:** a scanner can fail on a later token on the same flow line before it has reported the collections opened in front of it. The Python and Rust ports then re-parse only the text before the failing token. If that prefix already nests deeper than 64, the result is "nesting too deep", which keeps stream order and matches the JS port. An unclosed quote counts from where the quote opens.
- **Fixtures (22):** `invalid/alias-undefined.lock`, `invalid/precedence-anchor-beats-tag.lock`, `invalid/precedence-anchor-before-tag.lock`, `invalid/precedence-depth-beats-earlier-merge.lock`, `invalid/precedence-depth-before-syntax-multibyte.lock`, `invalid/precedence-depth-before-syntax-same-line.lock`, `invalid/precedence-depth-before-syntax.lock`, `invalid/precedence-depth-before-unclosed-quote.lock`, `invalid/precedence-invisible-key-before-tag.lock`, `invalid/precedence-merge-before-invisible-key.lock`, `invalid/precedence-printable-before-syntax.lock`, `invalid/precedence-profile-before-schema.yaml`, `invalid/precedence-schema-identifier-order.yaml`, `invalid/precedence-second-document-beats-earlier-tag.lock`, `invalid/precedence-syntax-beats-earlier-anchor.lock`, `invalid/precedence-syntax-beats-earlier-tag.lock`, `invalid/precedence-syntax-before-depth-same-line.lock`, `invalid/precedence-syntax-before-depth.lock`, `invalid/precedence-tag-before-alias.lock`, `invalid/precedence-tag-before-collection-key.lock`, `invalid/precedence-tag-before-duplicate.lock`, `invalid/precedence-undefined-alias-beats-earlier-tag.lock`
- **Tests:** JS `C-090 shared file cases` · Python `test_shared_file_cases[C-090]` · Rust `contract/files.rs::c090_first_violation_in_stream_order`

### C-091 Prototype-like keys are inert

- **Behavior:** Keys such as `__proto__`, `constructor` and `toString` are ordinary keys. They never satisfy a lookup for `hoshen`, `urim`, `dctp` or any other required key, and they never change how a value behaves. JS builds `Map`s, never plain objects.
- **Spec:** §5.1.1.
- **Fixtures (2):** `invalid/proto-key-not-urim.yaml`, `valid/proto-keys-inert.lock`
- **Tests:** JS `C-091 shared file cases` · Python `test_shared_file_cases[C-091]` · Rust `contract/files.rs::c091_prototype_keys_inert`

## 4. YAML syntax and values (any failure → `<file>: error: invalid YAML`)

### C-020 Syntax errors

- **Behavior:** Malformed YAML (unclosed flow, tab indentation, bad indentation, an alias to an undefined anchor) → `invalid YAML`. Parser details are left out so messages match across languages. Where a syntax error sits relative to a profile violation decides which is reported (C-090).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `invalid/syntax-error.yaml`, `invalid/tab-indent.yaml`
- **Tests:** JS `C-020 shared file cases` · Python `test_shared_file_cases[C-020]` · Rust `contract/files.rs::c020_syntax_error`

### C-021 Duplicate keys

- **Behavior:** Duplicate mapping keys at any depth → `invalid YAML`, including keys that resolve to the same value (`~`/`null`, `0x1`/`1`).
- **Spec:** §5.3 ("YAML 1.2 core schema"); rejecting duplicates is an implementation assumption.
- **Fixtures (3):** `invalid/duplicate-hex-decimal-key.yaml`, `invalid/duplicate-key.yaml`, `invalid/duplicate-null-key.yaml`
- **Tests:** JS `C-021 shared file cases` · Python `test_shared_file_cases[C-021]` · Rust `contract/files.rs::c021_duplicate_keys`

### C-022 Exactly one document

- **Behavior:** More than one document (including a trailing `---` that opens an empty second document) → `invalid YAML`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `invalid/multi-document.yaml`, `invalid/trailing-empty-document.lock`
- **Tests:** JS `C-022 shared file cases` · Python `test_shared_file_cases[C-022]` · Rust `contract/files.rs::c022_single_document`

### C-023 Scalar keys only

- **Behavior:** A sequence or mapping used as a mapping key, at any depth, → `invalid YAML`. JS and Python cannot represent these faithfully. An explicit key with no value (`? k`) is a key with a null value and is fine. A tagged collection key (`? !t [1]`, the B-2 regression) is now refused earlier as a tag (C-085).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `invalid/collection-key.lock`, `invalid/nested-collection-key.lock`, `valid/explicit-key-without-value.lock`
- **Tests:** JS `C-023 shared file cases` · Python `test_shared_file_cases[C-023]` · Rust `contract/files.rs::c023_collection_keys`

### C-024 64-bit integers

- **Behavior:** Every integer in the document must be in −2^63..2^64−1. Anything outside that range anywhere → `invalid YAML`. The bounds themselves parse (`hoshen: 18446744073709551615` → `unsupported hoshen version 18446744073709551615 (supported: 1)`).
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (6):** `invalid/hex-out-of-range.lock`, `invalid/hoshen-i64-min.lock`, `invalid/hoshen-u64-max.lock`, `invalid/int-below-i64-min.lock`, `invalid/int-out-of-range-elsewhere.lock`, `invalid/int-out-of-range.lock`
- **Tests:** JS `C-024 shared file cases` · Python `test_shared_file_cases[C-024]` · Rust `contract/files.rs::c024_int_range`

### C-025 Core-schema strings

- **Behavior:** YAML 1.2 core schema: `yes`/`no`/`on`/`off` and timestamps (`2026-10-25`) are strings; `true`/`True`/`TRUE` are booleans (so `urim: True` → `urim must be a string`). A `%YAML 1.1` directive does not switch to 1.1 booleans.
- **Spec:** §5.3 ("Contract parsers MUST use YAML 1.2 core schema").
- **Fixtures (4):** `invalid/lock-urim-true.lock`, `valid/urim-timestamp-is-a-string.lock`, `valid/urim-yes-is-a-string.decision.yaml`, `valid/yaml-1.1-directive-keeps-core-schema.lock`
- **Tests:** JS `C-025 shared file cases` · Python `test_shared_file_cases[C-025]` · Rust `contract/files.rs::c025_core_schema_strings`

### C-026 Integer forms

- **Behavior:** `0x` hex, `0o` octal and a `+` sign are integers (`hoshen: 0x1` is hoshen 1).
- **Spec:** §5.3 (core schema).
- **Fixtures (3):** `valid/hoshen-hex.lock`, `valid/hoshen-octal.lock`, `valid/hoshen-plus-sign.lock`
- **Tests:** JS `C-026 shared file cases` · Python `test_shared_file_cases[C-026]` · Rust `contract/files.rs::c026_int_forms`

### C-027 Non-integer lookalikes

- **Behavior:** Decimal with leading zeros (`01`), `0X1`, and `1_0` stay strings, so `hoshen: 01` → `hoshen must be an integer`. Leading zeros are an implementation assumption that matches serde_norway.
- **Spec:** §5.3 (core schema) plus implementation assumption.
- **Fixtures (3):** `invalid/hoshen-leading-zero.lock`, `invalid/hoshen-underscore.lock`, `invalid/hoshen-uppercase-hex-prefix.lock`
- **Tests:** JS `C-027 shared file cases` · Python `test_shared_file_cases[C-027]` · Rust `contract/files.rs::c027_non_int_forms`

### C-028 Floats are not integers

- **Behavior:** `1.0`, `1e0`, `.inf` are floats, so `hoshen` → `hoshen must be an integer`.
- **Spec:** §6.2 ("Integer format version").
- **Fixtures (3):** `invalid/hoshen-exponent.lock`, `invalid/hoshen-float.lock`, `invalid/hoshen-inf.lock`
- **Tests:** JS `C-028 shared file cases` · Python `test_shared_file_cases[C-028]` · Rust `contract/files.rs::c028_floats`

### C-029 Explicit core tags (retired)

- **Status:** retired in v0.0.2; replaced by C-085. Every tag, core tags included, is now refused with `tags are not allowed`. Its fixtures moved to C-085.

### C-030 Empty document is null

- **Behavior:** An empty file, a comments-only file, and a bare `---` are null → `root must be a mapping`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `invalid/comments-only.yaml`, `invalid/empty.yaml`, `invalid/explicit-empty-document.yaml`
- **Tests:** JS `C-030 shared file cases` · Python `test_shared_file_cases[C-030]` · Rust `contract/files.rs::c030_null_root`

### C-031 Root must be a mapping

- **Behavior:** A root that is a scalar or sequence → `<file>: error: root must be a mapping`. A flow mapping root is fine.
- **Spec:** §5.1 / §6.2 (top-level keys).
- **Fixtures (3):** `invalid/root-scalar.yaml`, `invalid/root-sequence.yaml`, `valid/flow-mapping-root.lock`
- **Tests:** JS `C-031 shared file cases` · Python `test_shared_file_cases[C-031]` · Rust `contract/files.rs::c031_non_mapping_root`

### C-032 Anchors and aliases (retired)

- **Status:** retired in v0.0.2; replaced by C-084. Anchors and aliases are now refused. `valid/anchor-alias.lock` moved to `invalid/anchor-alias.lock` under C-084.

### C-033 No merge keys (retired)

- **Status:** retired in v0.0.2; replaced by C-086. A `<<` key is now refused instead of being read as a literal key.

### C-034 Exact key spelling

- **Behavior:** Keys match exactly: `Hoshen`, `"hoshen "` and a quoted `"hoshen"` are compared as strings; integer key `1` differs from string key `"1"`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (2):** `valid/key-spellings.lock`, `valid/string-and-int-keys-distinct.lock`
- **Tests:** JS `C-034 shared file cases` · Python `test_shared_file_cases[C-034]` · Rust `contract/files.rs::c034_key_spelling`

### C-035 Keys of different types are distinct

- **Behavior:** Key equality includes the YAML type: `true` and `1`, or `1` and `1.0`, in the same mapping are distinct keys, not duplicates.
- **Spec:** §5.3 ("YAML 1.2 core schema"; under YAML 1.2, node equality includes the tag). Which keys count as duplicates is an implementation assumption, extending C-021. Added for bug B-1.
- **Fixtures (2):** `valid/bool-and-int-keys-distinct.lock`, `valid/int-and-float-keys-distinct.lock`
- **Tests:** JS `C-035 shared file cases` · Python `test_shared_file_cases[C-035]` · Rust `contract/files.rs::c035_keys_distinct_by_type`

## 5. Lockfile (root has `hoshen`)

### C-040 hoshen wins

- **Behavior:** If `hoshen` is present the file is a lockfile, even if `dctp`/`urim` contract keys are also present.
- **Spec:** §6.2 ("MUST read `hoshen` before anything else").
- **Fixtures (2):** `invalid/lockfile-dctp-is-not-urim.lock`, `valid/lockfile-wins-over-dctp.lock`
- **Tests:** JS `C-040 shared file cases` · Python `test_shared_file_cases[C-040]` · Rust `contract/files.rs::c040_hoshen_precedence`

### C-041 hoshen must be an integer

- **Behavior:** Strings, booleans, null, an empty value, sequences and mappings → `<file>: error: hoshen must be an integer`.
- **Spec:** §6.2 ("Integer format version").
- **Fixtures (6):** `invalid/hoshen-bool.lock`, `invalid/hoshen-empty-value.lock`, `invalid/hoshen-mapping.lock`, `invalid/hoshen-null.lock`, `invalid/hoshen-sequence.lock`, `invalid/hoshen-string.lock`
- **Tests:** JS `C-041 shared file cases` · Python `test_shared_file_cases[C-041]` · Rust `contract/files.rs::c041_hoshen_not_int`

### C-042 Unsupported hoshen

- **Behavior:** An integer outside the supported set → `<file>: error: unsupported hoshen version N (supported: 1)`, with N in decimal (`0x2` → `2`, `-0` → `0`). This names both versions.
- **Spec:** §6.2 ("MUST refuse, with an error naming both versions").
- **Fixtures (5):** `invalid/hoshen-negative-zero.lock`, `invalid/hoshen-negative.lock`, `invalid/hoshen-unsupported-hex.lock`, `invalid/hoshen-unsupported.lock`, `invalid/hoshen-zero.lock`
- **Tests:** JS `C-042 shared file cases` · Python `test_shared_file_cases[C-042]` · Rust `contract/files.rs::c042_hoshen_unsupported`

### C-043 urim required

- **Behavior:** No `urim` key → `<file>: error: missing required key(s): urim`.
- **Spec:** §6.2 (top-level `urim`).
- **Fixtures (1):** `invalid/lock-missing-urim.lock`
- **Tests:** JS `C-043 shared file cases` · Python `test_shared_file_cases[C-043]` · Rust `contract/files.rs::c043_urim_missing`

### C-044 urim must be a string

- **Behavior:** Integer, float, null or mapping `urim` → `<file>: error: urim must be a string`. YAML `0.1` unquoted is a float, so it's rejected.
- **Spec:** §6.2 (`urim` is `"0.1"`, a string).
- **Fixtures (4):** `invalid/lock-urim-int.lock`, `invalid/lock-urim-mapping.lock`, `invalid/lock-urim-not-string.lock`, `invalid/lock-urim-null.lock`
- **Tests:** JS `C-044 shared file cases` · Python `test_shared_file_cases[C-044]` · Rust `contract/files.rs::c044_urim_not_string`

### C-045 Lockfile ok

- **Behavior:** → stdout `<file>: ok (lockfile, hoshen N, urim V)`, exit 0. V is printed verbatim (an empty string is allowed). Other fields (`generated_at`, `compiler`, `contracts`) are not checked in v0.0.1.
- **Spec:** §6.2.
- **Fixtures (3):** `../spec/examples/urim.lock`, `valid/lock-urim-empty-string.lock`, `valid/minimal.lock`
- **Tests:** JS `C-045 shared file cases` · Python `test_shared_file_cases[C-045]` · Rust `contract/files.rs::c045_lockfile_ok`

### C-046 Lockfile check order

- **Behavior:** hoshen type → hoshen supported → urim present → urim type; the first failure wins.
- **Spec:** §6.2 (hoshen first); the rest of the order is an implementation assumption.
- **Fixtures (2):** `invalid/lock-order-hoshen-type-first.lock`, `invalid/lock-order-version-before-urim.lock`
- **Tests:** JS `C-046 shared file cases` · Python `test_shared_file_cases[C-046]` · Rust `contract/files.rs::c046_lockfile_order`

## 6. Contract (root has `dctp` or `urim`, no `hoshen`)

### C-050 Only one version key

- **Behavior:** Both `dctp` and `urim` → `<file>: error: set only one of 'dctp' or 'urim'`, checked before their types.
- **Spec:** §5.1 names `dctp`; accepting `urim` as an alias is an implementation assumption.
- **Fixtures (2):** `invalid/contract-both-keys-bad-types.decision.yaml`, `invalid/contract-both-version-keys.decision.yaml`
- **Tests:** JS `C-050 shared file cases` · Python `test_shared_file_cases[C-050]` · Rust `contract/files.rs::c050_contract_both_keys`

### C-051 Version key is a string

- **Behavior:** `<file>: error: dctp must be a string` (or `urim must be a string`).
- **Spec:** §5.1 (`dctp: "0.1"`).
- **Fixtures (3):** `invalid/contract-dctp-not-string.decision.yaml`, `invalid/contract-dctp-null.decision.yaml`, `invalid/contract-urim-not-string.decision.yaml`
- **Tests:** JS `C-051 shared file cases` · Python `test_shared_file_cases[C-051]` · Rust `contract/files.rs::c051_contract_key_type`

### C-052 Required keys

- **Behavior:** Any of `contract`, `version`, `state`, `questions` missing → `<file>: error: missing required key(s): a, b`, listing all missing keys in that order.
- **Spec:** §5.1 (REQUIRED keys).
- **Fixtures (3):** `invalid/contract-missing-all.decision.yaml`, `invalid/contract-missing-keys.decision.yaml`, `invalid/contract-missing-state-only.decision.yaml`
- **Tests:** JS `C-052 shared file cases` · Python `test_shared_file_cases[C-052]` · Rust `contract/files.rs::c052_contract_missing_keys`

### C-053 contract and version are strings

- **Behavior:** → `contract must be a string`, then `version must be a string` (contract is checked first). Kebab-case and semver formats are not checked.
- **Spec:** §5.1 / §6.1.
- **Fixtures (3):** `invalid/contract-id-checked-before-version.decision.yaml`, `invalid/contract-id-not-string.decision.yaml`, `invalid/contract-version-not-string.decision.yaml`
- **Tests:** JS `C-053 shared file cases` · Python `test_shared_file_cases[C-053]` · Rust `contract/files.rs::c053_contract_string_fields`

### C-054 state is a mapping

- **Behavior:** Anything that isn't a mapping → `<file>: error: state must be a mapping`. An empty mapping is fine.
- **Spec:** §5.2.
- **Fixtures (3):** `invalid/contract-state-not-mapping.decision.yaml`, `invalid/contract-state-null.decision.yaml`, `valid/contract-empty-state.decision.yaml`
- **Tests:** JS `C-054 shared file cases` · Python `test_shared_file_cases[C-054]` · Rust `contract/files.rs::c054_contract_state`

### C-055 questions is a non-empty mapping

- **Behavior:** → `<file>: error: questions must be a non-empty mapping`.
- **Spec:** §5.1 ("ordered map, >= 1") / §5.3.
- **Fixtures (3):** `invalid/contract-empty-questions.decision.yaml`, `invalid/contract-questions-null.decision.yaml`, `invalid/contract-questions-sequence.decision.yaml`
- **Tests:** JS `C-055 shared file cases` · Python `test_shared_file_cases[C-055]` · Rust `contract/files.rs::c055_contract_questions`

### C-056 Contract ok

- **Behavior:** → stdout `<file>: ok (contract ID@VERSION, KEY V)`, exit 0, values printed verbatim (multi-line strings included).
- **Spec:** §5.1.
- **Fixtures (4):** `../spec/examples/incident-triage.decision.yaml`, `../spec/examples/kyc-document-check.decision.yaml`, `valid/contract-multiline-id.decision.yaml`, `valid/minimal-urim.decision.yaml`
- **Tests:** JS `C-056 shared file cases` · Python `test_shared_file_cases[C-056]` · Rust `contract/files.rs::c056_contract_ok`

### C-057 Contract check order

- **Behavior:** both keys → key type → missing keys → contract type → version type → state → questions.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `invalid/contract-order-key-type-first.decision.yaml`, `invalid/contract-order-missing-before-types.decision.yaml`, `invalid/contract-order-state-before-questions.decision.yaml`
- **Tests:** JS `C-057 shared file cases` · Python `test_shared_file_cases[C-057]` · Rust `contract/files.rs::c057_contract_order`

## 7. Everything else

### C-060 Not a urim document

- **Behavior:** A mapping with none of `hoshen`/`dctp`/`urim` (including `{}` and provider descriptors) → `<file>: error: not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'`.
- **Spec:** Implementation assumption, not in spec.
- **Fixtures (3):** `../spec/examples/providers/cloudflare-clef-flash.provider.yaml`, `invalid/empty-mapping.yaml`, `invalid/unrecognized.yaml`
- **Tests:** JS `C-060 shared file cases` · Python `test_shared_file_cases[C-060]` · Rust `contract/files.rs::c060_not_urim`

## 8. Library API

### C-070 checkText / check_text

- **Behavior:** Validates text in memory. The file argument is used only in the message, and one leading BOM is stripped.
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `api.test.mjs` › `C-070 …` · Python `test_api.py::test_c070_check_text_uses_file_only_in_the_message` · Rust `contract/api.rs::c070_check_text_uses_file_only_in_message`

### C-071 Result shape

- **Behavior:** JS `{ok, line, exitCode}`; Python `CheckResult(ok, line)` with `.exit_code`; Rust `CheckResult { ok, line }` with `exit_code()`. Exit code is 0 iff ok, else 1.
- **Spec:** Implementation assumption, not in spec.
- **Tests:** JS `api.test.mjs` › `C-071 …` · Python `test_api.py::test_c071_result_carries_ok_line_and_exit_code` · Rust `contract/api.rs::c071_result_fields_and_exit_code`

### C-072 Constants

- **Behavior:** `SUPPORTED_HOSHEN` = {1} (JS `[1n]` bigint array, Python `frozenset({1})`, Rust `&[1]`). `VERSION` equals the package manifest version.
- **Spec:** §6.2 ("currently `1`").
- **Tests:** JS `api.test.mjs` › `C-072 …` · Python `test_api.py::test_c072_supported_hoshen_and_version` · Rust `contract/api.rs::c072_supported_hoshen_and_version`


### C-073 Typed problems (Rust API)

- **Behavior:** Every failing `CheckResult` carries a `Problem` (a `#[non_exhaustive]` enum implementing `std::error::Error`), and `"{file}: error: {problem}"` is exactly its `line()`. Passing results have no problem. `Display` propagates formatter errors and never panics.
- **Languages:** rust
- **Spec:** Implementation assumption, not in spec (Rust API guidelines C-GOOD-ERR).
- **Fixtures:** every case in `cases.json`.
- **Tests:** Rust `contract/api.rs::c073_problem_is_typed_and_displays_the_message`, `contract/api.rs::c073_problem_display_propagates_writer_errors`

## D. Known cross-language divergences (outside the conformance set)

These inputs behave differently across the three ports because the underlying YAML libraries differ. D-001..D-007 and D-010 were resolved by the v0.0.2 profile (§3) and are kept as stubs. D-008, D-009, D-011 and D-012 remain open. Every port **pins its own current behavior** from [`fixtures/divergences.json`](fixtures/divergences.json), so any change is deliberate. `parity.sh` skips them. Resolving each one is a behavior change for David to decide; a recommendation is given for each.

Tests: JS `test/divergences.test.mjs` › `D-0xx pinned JS behavior` · Python `tests/test_divergences.py::test_pinned_python_behavior[D-0xx]` · Rust `tests/contract/divergences.rs::d000_divergences_pin_rust_behavior` (all D cases).

### D-001 Unknown local tag on a scalar (resolved)

- **Status:** resolved in v0.0.2 by C-085: all three ports report `tags are not allowed` (fixture now `invalid/tag-custom-scalar.lock`).

### D-002 `!!int` on a non-numeric scalar (resolved)

- **Status:** resolved in v0.0.2 by C-085: `tags are not allowed` everywhere (`invalid/tag-int-non-numeric.lock`).

### D-003 `!!timestamp` / `!!binary` on `urim` (resolved)

- **Status:** resolved in v0.0.2 by C-085: `tags are not allowed` everywhere (`invalid/tag-timestamp.lock`, `invalid/tag-binary.lock`).

### D-004 Local tag on a mapping root (resolved)

- **Status:** resolved in v0.0.2 by C-085: `tags are not allowed` everywhere (`invalid/tag-custom-mapping.lock`).

### D-005 C0 control characters / NUL in the text (resolved)

- **Status:** resolved in v0.0.2 by C-082: `invalid YAML` everywhere, the recommended option (`invalid/control-char.lock`, `invalid/nul-byte.lock`).

### D-006 NEL (U+0085) in the text (resolved)

- **Status:** resolved in v0.0.2 by the C-082 extension: NEL is excluded from profile characters, so all three report `invalid YAML` (`invalid/next-line-char.lock`).

### D-007 Two leading BOMs (resolved)

- **Status:** resolved in v0.0.2 by the C-082 extension: exactly one leading BOM is stripped, and any further U+FEFF is `invalid YAML` everywhere, the first recommended option (`invalid/bom-not-leading.lock`).

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

### D-010 Alias expansion over 100 nodes (resolved)

- **Status:** resolved in v0.0.2 by C-084: anchors and aliases are refused, so all three report `anchors and aliases are not allowed` (`invalid/alias-expansion-over-100.lock`).

### D-011 Duplicate `.nan` keys

| fixture | JS | Python | Rust |
|---|---|---|---|
| `divergent/duplicate-nan-key.lock` | exit 0: `ok (lockfile, hoshen 1, urim x)` | exit 1: `error: invalid YAML` | exit 1: `error: invalid YAML` |

- **Why:** NaN ≠ NaN, so JS's uniqueness check passes them; PyYAML and serde_norway treat the two `.nan` keys as duplicates.
- **Recommendation:** Reject as duplicates (2 of 3, matching YAML's node-equality rule).

### D-012 Non-UTF-8 bytes in the path argument (POSIX)

| argv path bytes | JS | Python | Rust |
|---|---|---|---|
| `f\xff.lock` (exists, valid lockfile) | exit 1: `error: cannot read file` | exit 0: `ok (...)` | exit 0: `ok (...)` |

- **Why:** Node decodes argv to UTF-16 lossily (U+FFFD) before user code sees it, so the path it opens no longer exists. Python keeps the bytes through `surrogateescape`, and Rust's `args_os` keeps them in an `OsString`. How each prints the name is unified by C-089: undecodable bytes are shown as U+FFFD.
- **Recommendation:** Keep this. It's a platform limit in Node.
- **Tests:** JS `cli.test.mjs` "D-012 …", Python `test_cli.py::test_d012_non_utf8_path_argument`, Rust `contract/cli.rs::d012_non_utf8_path_argument`

## B. Bugs found by this suite

Each fix is its own commit, with the fixture failing before the fix and passing after it.

- **B-1 (Python): keys of different types compared equal.** `{true: a, 1: b}` and `{1: a, 1.0: b}` were rejected as duplicate keys (→ `invalid YAML`) because Python's `True == 1 == 1.0`. YAML node equality includes the tag, and JS and Rust accept both. Pinned as **C-035**; fixed in `src/urim/check.py` by comparing keys as `(type, value)`. Separate commit, failing then passing.
- **B-2 (Rust): a collection key under a local tag was accepted.** `? !t [1]` as a key passed in Rust, against C-023; JS and Python reject it. Pinned as fixture `invalid/tagged-collection-key.yaml` under C-023; fixed in `src/lib.rs` (`is_collection` looks through tags). Separate commit, failing then passing. Since v0.0.2 the fixture is refused earlier as a tag (C-085). `has_collection_key` in `src/profile.rs` still guards untagged collection keys (C-023).

## X. Coverage exclusions

No coverage-exclusion pragmas are used in any language. Code that coverage showed to be unreachable was deleted in the refactor commit, not excluded. Any future pragma must be listed here with its reason.
