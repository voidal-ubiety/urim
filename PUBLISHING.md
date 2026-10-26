# Publishing urim 0.0.1

Nothing here has been published or pushed yet. Run these commands yourself. Each registry claims the name on the **first successful publish**. Do the first publish of each package interactively from your own machine. Trusted publishing (CI) can be set up afterwards.

Before publishing, run every check from the repo root with one command:

```sh
scripts/verify.sh
```

It runs, in order: each package's tests with coverage enforced at 100% (JS c8; Python pytest-cov with branch coverage; Rust cargo-llvm-cov, with branch coverage on a nightly toolchain); `scripts/parity.sh`, which requires byte-identical output from all three CLIs; and `scripts/contract-check.py`, which requires every ID in [`CONTRACT.md`](CONTRACT.md) to have a test in every language. It needs node + npm, [uv](https://docs.astral.sh/uv/) (or `PYTHON=/path/to/venv/bin/python` with `pip install -e packages/python --group dev`; pip >= 25.1 reads dependency groups), and cargo with `cargo-llvm-cov`.

When you bump a version, update `fixtures/cli.json` (the `--version` cases) along with the three manifests.

## 1. GitHub (once github.com/no-complect/urim exists)

Create the repo empty, with no README or license, so the first push does not conflict. Then:

```sh
git remote add origin git@github.com:no-complect/urim.git
git push -u origin main
```

## 2. npm: `urim`

npm requires 2FA to publish. `npm login` creates a 2-hour session, and `npm publish` asks for a 2FA code. Classic tokens were revoked in Dec 2025.

```sh
npm login                         # account must have 2FA enabled
cd packages/js
npm ci
npm publish --access public       # prepack runs the TypeScript build; enter OTP when prompted
npm view urim                     # confirm
```

Optional, later: configure a trusted publisher (GitHub Actions OIDC) in the package settings on npmjs.com. It needs npm CLI >= 11.5.1 and Node >= 22.14. Then set Publishing access to "Require two-factor authentication and disallow tokens". The package has to exist before a trusted publisher can be set up, so the first publish has to be the manual one above.

## 3. PyPI: `urim`

PyPI requires 2FA on every account. You can upload two ways.

**A. API token with twine (simplest for the first upload)**

```sh
cd packages/python
rm -rf dist && python -m build
twine check dist/*
twine upload dist/*               # username: __token__  password: pypi-... (account-scoped token for the first upload)
```

Once the project exists, replace the account-wide token with one scoped to the project.

**B. Trusted publishing (GitHub Actions, no token).** On pypi.org, go to Account → Publishing → "Add a pending publisher". Enter project `urim`, owner `no-complect`, repo `urim`, and your workflow file name. Then publish from that workflow with `pypa/gh-action-pypi-publish`. A pending publisher does **not** reserve the name. The name is claimed only when the first upload succeeds, so use option A if you need the name right away.

## 4. crates.io: `urim`

crates.io accounts are created only through GitHub login, and you need a verified email on your crates.io account before you can publish.

```sh
# log in at https://crates.io with GitHub, verify email, create an API token (scope: publish-new, publish-update)
cargo login                       # paste the token
cd packages/rust
cargo publish --dry-run
cargo publish
```

Publishes to crates.io are permanent. A version can be yanked but never deleted, so check the dry run first.

## Order

The suggested order: GitHub push → npm → PyPI → crates.io. The repo URLs in every manifest point at github.com/no-complect/urim, so push first to avoid dead links. If claiming the names is urgent, publish the packages first. The links start working once the repo exists.

## Later releases

Bump the version in `packages/js/package.json`, `packages/python/pyproject.toml`, `packages/python/src/urim/__init__.py`, `packages/rust/Cargo.toml`, and `VERSION` in `packages/js/src/index.ts` (Rust reads its version from Cargo.toml). Then tag the release (`git tag v0.0.2 && git push --tags`).
