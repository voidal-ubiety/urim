# Urim

**Urim is a contract language for decision models.** Write it once, compile it to any provider, and prove behavior holds before you switch.

Decision models take application state plus typed questions (choice, score, yes/no) and return typed answers with probabilities. Vendors expose them through incompatible APIs and different confidence definitions. A Urim contract describes the decision once. The compiler targets each provider. A lockfile records the exact model, version, and per-model fitted thresholds, so a verdict can be reproduced.

<!-- generated:status (scripts/check-project --write) -->
> **Status: pre-alpha.** The protocol is SPEC v0.2.0-draft ([`spec/SPEC.md`](spec/SPEC.md)). v0.0.1 of the packages ships one small, working command, `urim check`, which validates `urim: "0.2"` contracts and `hoshen: 2` lockfiles against the closed 0.2 schemas. The compiler, `plan` and `apply` are not implemented yet.
<!-- /generated:status -->

## Names

Urim ships as **one package, `urim`**, on every registry. Thummim and hoshen are names inside it, not separate packages.

| Name | What it is | Status |
|---|---|---|
| **Urim** | The contract language, the compiler and the only package (`urim`) | pre-alpha; `urim check` works |
| **Thummim** | The eval and conformance suite: a module inside `urim`, kept behind its own module boundary | planned |
| **hoshen** | The lockfile format (`urim.lock`, top-level `hoshen: 2`) | specified in spec §6.2 |

## Install and use (v0.0.1)

```sh
npm install -g urim       # or: npx urim check <file>
pip install urim          # Python >= 3.10
cargo install urim
```

```sh
urim check fixtures/valid/minimal.lock
# fixtures/valid/minimal.lock: ok (lockfile, hoshen 2, urim 0.2)
urim check fixtures/valid/minimal-urim.decision.yaml
# fixtures/valid/minimal-urim.decision.yaml: ok (contract minimal@0.0.1, urim 0.2)
```

`urim check` exits 0 when the file is valid, 1 with a message naming the file and the problem when it isn't, and 2 on a usage error. The three implementations (TypeScript, Python, Rust) produce identical output on the shared fixtures in [`fixtures/`](fixtures/README.md). Every behavior is catalogued in [`CONTRACT.md`](CONTRACT.md), and `scripts/verify.sh` checks all of it.

## Command-line reference

<!-- generated:cli (scripts/check-project --write) -->
Generated from [`spec/SPEC.md` §7.4](spec/SPEC.md#74-resolver-and-cli-flags) by `scripts/check-project --write`. Only the rows marked **Implemented** exist today. Anything Planned or PROPOSED is not in the CLI yet: the CLIs reject it as a usage error (exit 2), and `fixtures/cli.json` tests that.

| Flag or key | Applies to | Status | What it does | Why it exists |
|---|---|---|---|---|
| `--strict-prefers` | `urim compile`, `urim plan` | **Planned** (D-15) | Treats every `prefers` entry's fallback as `fail` for this run. Resolution then fails, with `capability_unsupported`, for each target that would need an `emulate:` or `drop` fallback, and the report lists each (target, capability path) pair. A passing run means every preferred feature resolved `native` on every target. It never edits the contract and never writes or changes the lockfile. | `fail` in a contract is the author's choice for one entry. Operators and CI also need a portability check, "would this contract work without any emulation or dropped feature?", without editing contracts. Being a run flag, not a contract key, it cannot change what is deployed. |
| `--version`, `-V` | `urim` | Implemented | Prints `urim <VERSION>` and exits 0. | Standard tool identification. |
| `--help`, `-h` | `urim` | Implemented | Prints the usage line and exits 0. | Standard usage help. |
| `urim check <file>` | `urim` | Implemented | Checks one file and reports errors in the documented format. | The only subcommand today. It validates `urim: "0.2"` contracts and `hoshen: 2` lockfiles. |
| `urim migrate` | contracts, lockfiles | **Planned**; name TODO (§5.10.4) | Rewrites a v0.1 contract to 0.2 (`urim:` key, `requires`/`prefers` with explicit fallbacks) and a `hoshen: 1` lockfile to `hoshen: 2`. | v0.1 keys are `invalid_contract` in 0.2, and the error names this command, so every user has a mechanical path. |
| `selection` (contract key) | runtime | Defined; `available` PROPOSED (§5.10.6) | `strict` (absent meaning): use `active`, then `standby` only under §D.2. `available`: MAY skip a locked target that has no usable credential. | Credentials may select among planned targets but never unlock an unplanned feature or target. |
| `URIM_TARGET` (env) | runtime | **Planned**; name TODO (§5.10.6) | Pins one target; it MUST name a lockfile target, otherwise `lock_violation`. | Debugging and staged rollouts without editing the lockfile. |
| `telemetry.mapping` (config) / `URIM_TELEMETRY_MAPPING` (env) | runtime | **Planned**; names PROPOSED (§D.3.6) | Selects the telemetry mapping: an exact version, a MINOR line, or `latest`. Unset: the package's documented default. | Telemetry renames must never touch contracts or lockfiles; users opt in to new names. |
| `telemetry.emit_deprecated` (config) | runtime | **Planned**; name PROPOSED (§D.3.6) | `false` turns off dual-emit of deprecated names early. | Avoids doubled metric series for users who have already migrated dashboards. |

Rules:

1. No flag, environment variable, or configuration key may enable hedging, per-question failover, failover on `lock_violation`, or a target or feature outside the lockfile (spec §D.2.1, §5.10.6).
2. A flag that changes resolution (today only `--strict-prefers`) MUST be printed in the `plan` report header, so a report can be reproduced.
3. Every new flag or key MUST be added to this table, with its reason, in the same change that adds it.
<!-- /generated:cli -->

## Repository layout

```
spec/                 the protocol spec (version in Status above), changelog, examples
fixtures/             shared conformance cases for `urim check`
packages/js           npm package `urim` (TypeScript, ESM)
packages/python       PyPI package `urim`
packages/rust         crates.io crate `urim`
scripts/              verify.sh (all tests, 100% coverage, parity, contract check)
CONTRACT.md           the behavior contract: every rule with an ID, spec reference and tests
PUBLISHING.md         exact publish/push commands (nothing published yet)
```

## A note on the name

The Urim and Thummim appear in Exodus 28:30, carried in the breastpiece (the *hoshen*) of the high priest. They carry religious significance in Jewish, Christian, and Latter-day Saint traditions. This project borrows only the idea of asking a question and receiving a verdict, and uses the names with respect. No religious claim or affiliation is intended.

## Prior art and credits

- **Decision Model Protocol (DMP) draft 0.1:** <https://decisionmodelprotocol.io/specification/0.1>. Urim's response rules follow it where they overlap.
- **jevcompat:** conformance testing for Jev-compatible servers.
- **sys1bench:** calibration benchmarks for decision models.
- **Buf `protoc-gen-jev`:** Protobuf code generation for Jev requests.
- **Jev Harness:** built by David Thomason on TypeSafe's Jev; the motivating reference application.

Jev is a product of TypeSafe. Other vendor and product names belong to their owners. Mentioning them implies no endorsement.

## Links

<!-- generated:links (from config/project.json) -->
- Homepage: <https://urim.sh>
- Repository: <https://github.com/voidal-ubiety/urim>
<!-- /generated:links -->

## Contributing and security

- [CONTRIBUTING.md](CONTRIBUTING.md): setup, the dependency policy and sign-off (DCO).
- [SECURITY.md](SECURITY.md): how to report a vulnerability, and the limits `urim check` enforces.

## License

Apache-2.0. See [LICENSE](LICENSE). Copyright 2026 David Thomason and Urim contributors.
