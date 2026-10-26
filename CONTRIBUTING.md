# Contributing to Urim

Thanks for helping. This file covers what ships, how to set up, how a change is made, the dependency policy, the commit sign-off (DCO), the rule for agent-written commits, and where security reports go.

## What ships

One package, `urim`, published as `urim` on npm, PyPI and crates.io, and as `@urim/urim` on JSR. Thummim and Hoshen are internal names (the checker module and the lockfile format). They are not separate packages, and a change must not add a package or registry name for them.

## Setup

You need:

- Node.js 22 or 24, with npm (`engines` is `>=22`, and CI tests both).
- [uv](https://docs.astral.sh/uv/) for Python 3.10 or later.
- rustup with the stable (plus clippy and rustfmt), nightly (branch coverage) and 1.85.0 (MSRV) toolchains.
- `cargo-llvm-cov`, `cargo-deny` and `cargo-audit`.
- `strace`, for `scripts/check-sandbox`. It is optional locally and required by `--release`.

Run the single gate from anywhere in the checkout:

```sh
scripts/verify.sh            # everything: lint, types, 100% coverage, parity, hostile suite
scripts/verify.sh --release  # also the release gates (DCO sign-off, audit-legal --release)
```

The full run takes a few minutes. `.github/workflows/ci.yml` runs the same script.

## Making a change

- **Contract first.** `CONTRACT.md` is the behavior contract for all three ports (`packages/js`, `packages/python`, `packages/rust`). A behavior change starts there: update the C-xxx entry, add fixtures to `fixtures/cases.json`, then change all three ports. `scripts/contract-check.py` fails if an ID is not tested in every port it applies to, or if a fixture list drifts from `cases.json`.
- **Parity.** The three CLIs must print byte-identical output for every fixture (`scripts/parity.sh`). Known library differences are pinned as D-xxx entries in `fixtures/divergences.json`, so changing one is deliberate.
- **Coverage.** Each port stays at 100% line, branch and function coverage.
- **Bugs.** Write the failing test first, then the fix, as its own commit that says what was wrong. CONTRACT.md § B lists the earlier ones.
- **Generated files.** Do not hand-edit generated files: `schema/` ports, the README generated blocks, `config/deps-allowlist.json`, `CODEOWNERS`. Each has a `--write` generator and a `--check` in `verify.sh`.
- **Spec copies.** `spec/` is an exact copy of the upstream decision-contract-spec repository (`scripts/sync-spec` checks the hashes). Change the spec upstream, not here.
- **Agents** also follow [`docs/agents/self-check.md`](docs/agents/self-check.md) before asking for review.

## Dependency policy

Every runtime dependency is attack surface for a tool that reads untrusted files, so the bar for adding one is high.

- **Minimal runtime closure.** One YAML parser per port and nothing else at runtime: `yaml` (JS), `pyyaml` (Python), `saphyr-parser` (Rust). Do not add a second YAML parser. `deny.toml` bans the known ones (`serde_yaml`, `serde_norway`, `unsafe-libyaml`, `yaml-rust`).
- **Locked and allowlisted.** `package-lock.json`, `uv.lock` and `Cargo.lock` are committed. `scripts/check-deps` compares their runtime closures with `config/deps-allowlist.json` (version plus integrity or checksum) and fails on any change. To accept a change, run `scripts/check-deps --write` and explain each diff line in the commit message.
- **Exact pin where the parser's behavior is the contract.** `saphyr-parser` is pinned `=0.2.2` because its event stream defines what the Rust port accepts. The JS `yaml` range is `^2.9.1`; the lockfile and allowlist hold it at 2.9.1.
- **No install-time code.** npm installs run with `--ignore-scripts`, and `check-deps` fails if any npm package in the lock declares an install script. New Rust build scripts or proc-macros show up in the `check-deps` output and need a reason.
- **Licenses.** Only licenses allowed by `docs/legal/license-policy.yaml` (`cargo deny` for Rust, `scripts/audit-legal` for all three).
- **Sources.** crates.io, the npm registry and PyPI only. No git or path dependencies in anything that ships.

See SECURITY.md § Supply chain for what each check detects and what it cannot.

## Sign-off (Developer Certificate of Origin)

Contributions are accepted under the Apache License 2.0 (inbound = outbound, Apache-2.0 §5). Every commit must carry a `Signed-off-by` trailer that matches the commit author, certifying the Developer Certificate of Origin 1.1 (also in [`docs/legal/DCO-1.1.txt`](docs/legal/DCO-1.1.txt)):

> Developer Certificate of Origin
> Version 1.1
>
> Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
>
> Everyone is permitted to copy and distribute verbatim copies of this
> license document, but changing it is not allowed.
>
>
> Developer's Certificate of Origin 1.1
>
> By making a contribution to this project, I certify that:
>
> (a) The contribution was created in whole or in part by me and I
>     have the right to submit it under the open source license
>     indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best
>     of my knowledge, is covered under an appropriate open source
>     license and I have the right under that license to submit that
>     work with modifications, whether created in whole or in part
>     by me, under the same open source license (unless I am
>     permitted to submit under a different license), as indicated
>     in the file; or
>
> (c) The contribution was provided directly to me by some other
>     person who certified (a), (b) or (c) and I have not modified
>     it.
>
> (d) I understand and agree that this project and the contribution
>     are public and that a record of the contribution (including all
>     personal information I submit with it, including my sign-off) is
>     maintained indefinitely and may be redistributed consistent with
>     this project or the open source license(s) involved.

Add the trailer with `git commit -s`. It uses your `user.name` and `user.email`, which must be the commit's author name and email. To sign off commits you already made on your branch, run `git rebase --signoff <base>`.

`scripts/check-dco` checks every non-merge commit. It runs in `scripts/verify.sh --release` and `.github/workflows/ci.yml`.

## Commits written by an agent

An AI agent cannot certify the DCO. It is not a person, and it cannot know where the code came from in the sense the certificate requires. So:

- An agent must **never** add a `Signed-off-by` line, for itself or for anyone else.
- A human who has read the change and can make the certification signs it off: the agent's commits go to a branch, the human reviews them and runs `git rebase --signoff <base>` (or `git commit --amend -s`), and then they are pushed or merged.
- Until that sign-off, `scripts/check-dco` fails on those commits, as intended.

## Security issues

Do not open a public issue. See [SECURITY.md](SECURITY.md).
