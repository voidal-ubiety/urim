# Publishing urim 0.0.1

> Nothing here has been published or pushed. David runs every command in this file himself. Each registry gives the name to whoever publishes it first, so do the first publish of each package by hand from your own machine. Trusted publishing (CI) comes after that. The full release procedure, including the history rewrite (§3a), is `/workspace/urim-shipping/RELEASE-RUNBOOK.md`. This file does not repeat it.

Only one package ships, named `urim`, on every registry: npm `urim` (unscoped), PyPI `urim`, crates.io `urim` and JSR `@urim/urim`.

## 0. Checks

Run these from the repo root:

```sh
scripts/verify.sh            # tests at 100% coverage in all three ports, parity, contract, generated-file and project checks
scripts/verify.sh --release  # also the DCO check and scripts/audit-legal --release (M3 fails until the §3a history rewrite; the 10 rules not yet built fail in --release; run it online, since L5-Py needs PyPI)
```

`scripts/check-project` fails if the version differs anywhere it appears. That covers `packages/js/package.json`, `package-lock.json`, `jsr.json`, `VERSION` in `src/index.ts`, `pyproject.toml`, `__version__`, `Cargo.toml` and `Cargo.lock`. Rust reads its version from Cargo.toml. It also fails if the README status lines are out of date with `spec/SPEC.md`, or if any manifest URL differs from `config/project.json`.

## 1. Project URLs: one value

The repository URL lives in `config/project.json` (`repository`), and so do `homepage` and `documentation` (both `https://urim.sh`). To move the repo, edit that file, run `scripts/check-project --write`, and commit. The script rewrites:

- `packages/js/package.json`: `homepage`, `repository.url`, `bugs.url`
- `packages/python/pyproject.toml`: `[project.urls]` Homepage, Documentation, Repository, Issues
- `packages/rust/Cargo.toml`: `homepage`, `repository`, `documentation`
- the `<!-- generated:links -->` blocks in `README.md` and `packages/*/README.md`

The repository owner is the GitHub organisation **`voidal-ubiety`** (public repo `voidal-ubiety/urim`), the name of the future holding company (David, t64u/t65u). The homepage stays `https://urim.sh`. `check-project` fails if any other file hard-codes the owner, or if any `github.com/<owner>/urim` URL names a different owner.

Remaining spots that name a GitHub account. They are not the repository URL, so they are not changed:

- `spec/SPEC.md`, line 6: the Author row, `David Thomason (github.com/no-complect)`, is David's personal GitHub account, not the repo owner. It is also a copy of the upstream decision-contract-spec SPEC.md, so it must not be edited here.
- `config/people.yaml`: David's personal GitHub handle for CODEOWNERS (see "People" below).
- Outside this repo: `/workspace/decision-contract-spec/SPEC.md`, the upstream file (read-only for agents).
- Sigstore provenance or attestations for any version published from CI record the repo owner permanently (RELEASE-RUNBOOK §7, L9). Publish from CI only after the repo is under `voidal-ubiety`.

People: names, emails and GitHub handles live in `config/people.yaml`. Edit it and run `scripts/gen-codeowners --write` to regenerate `.github/CODEOWNERS`. `verify.sh` fails if they drift. CODEOWNERS entries must be users or `@org/team` handles with write access to the repo; a bare organisation name is not a valid owner.

Spec copy flagged for an upstream fix (do not edit `spec/` here):

- `spec/SPEC.md` §7.4, row `urim check <file>`: "It does not yet accept the 0.2 keys (CHANGELOG.md, "Known conflicts")." The ports in this repo now accept 0.2. The README's generated CLI reference swaps that sentence for the current one (`STALE_CHECK_NOTE` in `scripts/check-project`). Once upstream fixes it and `scripts/sync-spec` re-copies, delete the override.

## 2. GitHub

Create the repo empty and **public** under the `voidal-ubiety` organisation, with no README or license, so the first push doesn't conflict (David only; nothing has been created):

```sh
git remote add origin "$(scripts/check-project --get repository).git"
git push -u origin main
```

Check before the first push (public, read-only lookups on 2026-10-26, last at 13:41 EDT): `voidal-ubiety` is a GitHub **Organization** (id 348431208, created 2026-10-26 13:13 EDT). The earlier `voidal-ubiety` user account (created 2025-04-25) was renamed `vu-control` (User, id 209141439; same id and creation date), which settles P8 (`/workspace/urim-shipping/RELEASE-RUNBOOK.md` §3b0) as an organisation. The stated org owners are `no-complect` and `vu-control`. The public API can't confirm this: the org shows no public members. `voidal-ubiety/urim` will be **public**. The website is a separate **private** repo, `voidal-ubiety/urim-site`, and nothing from it belongs in this repo. Neither repo is visible yet (both return 404, as expected for a repo that doesn't exist or is private). `config/people.yaml` keeps David's personal handle `no-complect`, which stays valid for CODEOWNERS. Now that the owner is an organisation, CODEOWNERS may instead use `@voidal-ubiety/<team>` handles, once such a team exists with write access.

npm provenance needs a **public** repo. npm does not generate provenance for private repositories, even when the package is public (https://docs.npmjs.com/trusted-publishers).

## 3. npm: `urim`

```sh
npm login                         # 2FA required
cd packages/js && npm ci --ignore-scripts && npm run build
npm pack --dry-run                # check the file list: dist/, README.md, LICENSE, NOTICE, package.json
npm publish                       # prepack builds; enter the OTP. No --access flag: `urim` is unscoped, so it is public
npm view urim
```

`engines.node` is `>=22`. Node 18 reached end of life on 2025-04-30 and Node 20 on 2026-04-30 (https://nodejs.org/en/about/previous-releases).

Trusted publishing, later: the package must exist first. Use npm CLI ≥ 11.5.1 and Node ≥ 22.14.0 (`.github/workflows/publish.yml` pins these). A new trusted-publisher config **expires unless its first publish succeeds within 2 days**, so tag and publish from CI right after you create it. After that, set Publishing access to "Require two-factor authentication and disallow tokens" and revoke any tokens.

Reversibility: you can unpublish within 72 h if nothing depends on the package. `urim@0.0.1` can never be reused (https://docs.npmjs.com/policies/unpublish).

## 4. PyPI: `urim`

```sh
cd packages/python && rm -rf dist && python -m build && twine check dist/*
twine upload dist/*               # __token__ + an account-scoped token for the first upload; scope it to the project afterwards
```

A pending trusted publisher does **not** reserve the name. Deleting a release is permanent and frees the name for anyone. Yank instead.

## 5. crates.io: `urim`

```sh
cargo login                       # token from crates.io (GitHub login, verified email)
cd packages/rust && cargo package --list && cargo publish --dry-run && cargo publish
```

The first publish needs an API token. Trusted publishing (`rust-lang/crates-io-auth-action@v1`) can be configured only once the crate exists. Deletion is possible only within 72 h of publishing, or when the crate has a single owner, fewer than 1000 downloads for each month it has been published, and no reverse dependencies. Otherwise yank (`cargo yank --version 0.0.1`). The code stays downloadable (https://crates.io/policies, checked 2026-10-26).

## 6. JSR: `@urim/urim`

`packages/js/jsr.json` names the package `@urim/urim`, and its version is checked against package.json. The `@urim` scope was free at the 2026-10-26 10:47 ET scan. Create the scope only when David says yes.

```sh
cd packages/js && npx jsr publish --dry-run   # UNVERIFIED: not run yet (it needs network); check that the .js import specifiers resolve to src/*.ts and that `yaml` resolves via package.json
npx jsr publish
```

JSR is immutable. A scope admin can delete a version only within 24 h, and only if it has almost no downloads and no dependents need it (https://jsr.io/docs/immutability). Otherwise yank.

## 7. Order and tags

The order is GitHub push, then npm, PyPI, crates.io and JSR. Tag each release signed, after its notes are in `CHANGELOG.md`:

```sh
git tag -s v0.0.2 -m v0.0.2 && git push origin v0.0.2
```

When you bump the version, change every file listed in §0 (`scripts/check-project` lists any you missed), plus the `--version` cases in `fixtures/cli.json`.
