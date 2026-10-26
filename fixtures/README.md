# Shared fixtures for `urim check`

All three implementations (`packages/js`, `packages/python`, `packages/rust`) run every case in `cases.json` and must produce **exactly** the same exit code and output line.

## Behavior of `urim check <file>` (v0.0.1)

Output is one line: `<file>: ok (...)` on stdout with exit 0, or `<file>: error: <problem>` on stderr with exit 1. Usage errors exit 2.

Checks run in this order. The first failure wins.

1. Read the file and decode it as UTF-8 (strict); a leading BOM is ignored. Failures: `cannot read file`, `file is not valid UTF-8`.
2. Parse exactly one YAML document using **YAML 1.2 core-schema** scalars (`yes`/`no`/`on`/`off` are strings, timestamps are strings). Integers follow the core schema (`0x`/`0o` forms allowed) except that decimal integers with leading zeros (`01`) stay strings. Duplicate keys, multiple documents, sequence/mapping keys, and integers outside the 64-bit range (−2^63 to 2^64−1) count as parse errors. Failure: `invalid YAML` (parser details are left out so the messages match across languages).
3. The root must be a mapping. An empty file counts as null. Failure: `root must be a mapping`.
4. **Lockfile:** applies if the root has `hoshen`.
   1. `hoshen` must be an integer (booleans and floats such as `1.0` are rejected).
   2. It must be in the supported set `{1}`.
   3. The `urim` key must be present and must be a string.

   OK output: `ok (lockfile, hoshen N, urim V)`.
5. **Contract:** applies if the root has `dctp` or `urim` (but not `hoshen`).
   1. The root must not have both `dctp` and `urim`.
   2. That key's value must be a string.
   3. `contract`, `version`, `state` and `questions` must be present. All missing keys are listed, in that order.
   4. `contract` and `version` must be strings.
   5. `state` must be a mapping.
   6. `questions` must be a non-empty mapping.

   OK output: `ok (contract ID@VERSION, KEY V)`.
6. Anything else: `not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'`. That includes provider descriptors, which v0.0.1 does not check.

Known limits: anything not covered by `cases.json` (e.g. merge keys `<<`, unusual tags, `.inf`/`.nan`) is outside the conformance set. `scripts/parity.sh` runs all three CLIs over every case and requires byte-identical output.
