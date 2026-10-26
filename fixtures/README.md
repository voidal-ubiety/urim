# Shared fixtures for `urim check`

All three implementations (`packages/js`, `packages/python`, `packages/rust`) run every case in `cases.json` and must produce **exactly** the same exit code and output line.

## Behavior of `urim check <file>` (v0.0.1)

Output is one line: `<file>: ok (...)` on stdout with exit 0, or `<file>: error: <problem>` on stderr with exit 1. Usage errors exit 2.

Checks run in this order. The first failure wins.

1. Read the file and decode it as UTF-8 (strict); a leading BOM is ignored. Failures: `cannot read file`, `file is not valid UTF-8`.
2. Parse exactly one YAML document using **YAML 1.2 core-schema** scalars (`yes`/`no`/`on`/`off` are strings, timestamps are strings). Integers follow the core schema (`0x`/`0o` forms allowed) except that decimal integers with leading zeros (`01`) stay strings. Duplicate keys, multiple documents, sequence/mapping keys, and integers outside the 64-bit range (−2^63 to 2^64−1) count as parse errors. Failure: `invalid YAML` (parser details are left out so the messages match across languages).
3. The root must be a mapping. An empty file counts as null. Failure: `root must be a mapping`. The version key's pre-0.1 name is refused here, before anything else (C-093; see CONTRACT.md for the message).
4. **Lockfile:** applies if the root has `hoshen`.
   1. `hoshen` must be an integer (booleans and floats such as `1.0` are rejected).
   2. It must not be 1, a format that was never released (C-094), and must be in the supported set `{2}`.
   3. The `urim` key must be present and must be a string.

   OK output: `ok (lockfile, hoshen N, urim V)`.
5. **Contract:** applies if the root has `urim` (but not `hoshen`).
   1. `urim` must be a string.
   2. `contract`, `version`, `state` and `questions` must be present. All missing keys are listed, in that order.
   3. `contract` and `version` must be strings.
   4. `state` must be a mapping.
   5. `questions` must be a non-empty mapping.

   OK output: `ok (contract ID@VERSION, urim V)`.
6. Anything else: `not a urim document: expected a lockfile with 'hoshen' or a contract with 'urim'`. That includes provider descriptors, which v0.0.1 does not check.

## Files

- `cases.json`: file-level cases (`urim check <path>`). Each case has the `id` of the [`CONTRACT.md`](../CONTRACT.md) entry it pins.
- `cli.json`: argv-level cases (flags, usage errors, stdout vs stderr, verbatim paths), run with this directory as cwd.
- `divergences.json` + `divergent/`: inputs where the ports knowingly differ (CONTRACT.md section D). Each port pins its own behavior; `scripts/parity.sh` skips them.

`scripts/parity.sh` runs all three CLIs over every `cases.json` and `cli.json` case and requires byte-identical output. [`CONTRACT.md`](../CONTRACT.md) is the full catalog.
