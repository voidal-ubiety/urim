# Security policy

## Reporting a vulnerability

Email **hello@davidthomason.dev** with "urim security" in the subject. Include the affected package (`urim` on npm, PyPI or crates.io, or the JSR package `@urim/urim`), the version, and a minimal input file or steps that reproduce the problem.

Please do not open a public issue for a vulnerability. GitHub private vulnerability reporting will be listed here as a second channel once it is enabled on the repository; until then, email is the only channel.

## Supported versions

Urim is pre-1.0 (0.0.x on the registries). Only the latest published version gets fixes. Security fixes are handled on a best-effort basis by a single maintainer. There is no response-time or fix-time commitment.

## What `urim check` is designed to resist

`urim check` reads untrusted contract and lockfile text. The three ports (JS, Python, Rust) are built to the same contract (CONTRACT.md), and the same hostile inputs test all three.

| Limit | Value | Contract |
|---|---|---|
| Input size | 1,048,576 bytes (`MAX_BYTES`), checked before parsing | C-080 |
| Nesting depth | 64 collections, root mapping = 1 (`MAX_DEPTH`) | C-083 |
| Anchors, aliases, tags | refused | C-084, C-085 |
| Characters | YAML 1.2 `c-printable` only; NEL, LS, PS and non-leading BOM refused | C-082 |
| File type | regular files only; FIFOs, sockets, devices and directories refused without blocking (symlinks are followed, then the target is checked) | C-081 |
| Mapping keys | invisible and bidirectional-control characters refused | C-087 |
| Terminal output | C0/C1 controls, DEL, lone surrogates and the C-087 characters in the file name and echoed values or keys are escaped as `\u{XXXX}` | C-089 |

The values live in each port's `limits` module (`packages/js/src/limits.ts`, `packages/python/src/urim/limits.py`, `packages/rust/src/limits.rs`).

### Hostile-input suite

`scripts/hostile.py` (run by `scripts/verify.sh`) runs every case in `fixtures/hostile.json` plus `fixtures/hostile/*` through all three CLIs. For each run it checks the exit code and exact output, a per-port time and peak-RSS bound, and that the canary file `/tmp/urim-hostile-canary` was not created. Default bounds: JS 4000 ms / 256 MiB, Python 6000 ms / 192 MiB, Rust 3000 ms / 96 MiB. A case may raise a bound; every raised bound carries a `bounds_note` explaining why.

### Open findings (resource use inside the limits)

These inputs are accepted or rejected correctly, but they cost more than the default bounds. They are recorded here rather than hidden by a bound:

- **JS memory on large flow collections.** The npm `yaml` package builds a document model of about 1 KiB per node. Inputs inside `MAX_BYTES` reach roughly 0.3 to 1 GiB peak RSS (`deep-flow-sequence-million`, `deep-flow-closed`, `alias-flood`, `deep-flow-mapping`, `many-documents`; see their bounds in `fixtures/hostile.json`).
- **Wide flow sequences.** At 450k items (900 KB, inside `MAX_BYTES`), measured on 2026-10-26: JS 2.5 s / 548 MiB, Python 17.5 s / 296 MiB (PyYAML's pure-Python parser, linear at about 28 µs per item), Rust 0.9 s / 103 MiB. The suite case uses 150k items.

A caller that checks untrusted files at volume should apply its own process time and memory limits.

## Supply chain

Each check below runs in `scripts/verify.sh` unless noted. Each one is a tripwire: it detects a specific change and fails the build. None of them proves a dependency is safe.

| Check | Detects | Does not detect |
|---|---|---|
| `scripts/check-deps` against `config/deps-allowlist.json` | Any change to the runtime dependency closure (name, version, integrity or checksum) in `package-lock.json`, `uv.lock` or `Cargo.lock`; any npm package with an install script; new Rust build-time code (build scripts, proc-macros) | Malicious code in a version that is already allowlisted; it checks lockfiles, not what an installer fetched |
| `cargo deny check` (`packages/rust/deny.toml`) | RustSec advisories, licenses outside the allow list, banned or duplicate crates, sources other than crates.io | Unreported vulnerabilities; JS and Python dependencies |
| `cargo audit -D warnings` | RustSec advisories against `Cargo.lock`, including warnings | Same as above |
| `scripts/check-sandbox` (needs `strace`; skipped without it, required with `--release`) | Network syscalls, child processes and file writes by any of the three CLIs while checking the valid and hostile fixtures | Behavior on inputs it does not run, other platforms, or code paths only reached under conditions the fixtures do not cover |
| `npm ci --ignore-scripts` (CI and `verify.sh`) | Prevents install-time scripts from running during the dev install | Code that runs later at build or test time |
| `scripts/audit-legal` | License and attribution gates for the shipped packages (`docs/legal/license-policy.yaml`) | Security issues |

Not run today: `npm audit` and `pip-audit`. Both need network access to an advisory database, and `verify.sh` runs offline. The JS and Python runtime closures are one package each (`yaml`, `pyyaml`). Until an advisory check is added, they are reviewed by hand when `check-deps` flags a change.

Dependency changes follow [CONTRIBUTING.md § Dependency policy](CONTRIBUTING.md#dependency-policy).
