# Changelog

Release notes for the `urim` packages (npm, PyPI, crates.io, JSR). They all share one version (`scripts/check-project`). The protocol's own history is in [`spec/CHANGELOG.md`](spec/CHANGELOG.md).

## Unreleased (0.0.1)

Nothing has been published yet.

### Protocol
- `urim check` validates `urim: "0.2"` contracts and `hoshen: 2` lockfiles against SPEC v0.2.0-draft. That covers the version gate (C-100), the closed schemas generated from `schema/urim-0.2.json` (C-095, C-096), contract rules (C-097), the lockfile seal (C-098) and lockfile rules (C-099).
- The version key is `urim` only. `hoshen: 1` was never released and is rejected (C-093, C-094).
- `spec/` is a byte-for-byte copy of decision-contract-spec. `scripts/sync-spec` checks it against the hashes in `spec/SOURCE.json`.

### Behavior across the three ports
- The JS, Python and Rust CLIs produce byte-identical output for every invocation in `fixtures/` (`verify.sh` parity step).
- Known divergence D-015 (CONTRACT.md): the Python port rejects a plain scalar containing `?` inside a flow collection (`{a: b?}`), which SPEC §4 says must be accepted. The fixture pins this; it is not fixed yet. Workaround: use quotes or block style.

### Tooling and hardening
- The hostile-input suite (`scripts/hostile.py`) runs under time and memory bounds and never executes input. A strace sandbox check shows no network, child processes or file writes.
- A runtime dependency allowlist (`scripts/check-deps`). Node `>=22`.
- `scripts/audit-legal`, the legal and naming gate, with rules L1, L2, L4, L5-Rust, L5-Py, M1, M3, M5, C1, C3, C4, T1, T4 and T5. The rest report SKIP in a normal run and FAIL with `--release`, so a release can't pass until every rule is built. The marks register is in `docs/legal/marks.yaml`.
- The README's command-line reference is generated from SPEC §7.4. Only `--version`/`-V`, `--help`/`-h` and `urim check` exist; every other command and flag is marked Planned and exits 2.
- Project URLs come from one value in `config/project.json`. The repository is `voidal-ubiety/urim` on GitHub and the homepage is https://urim.sh. CODEOWNERS is generated from `config/people.yaml`.
- DCO sign-off is required (ADR 0003, `scripts/check-dco` in `verify.sh --release`).
