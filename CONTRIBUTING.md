# Contributing to Urim

Thanks for helping. This file covers what ships, setup, how to make a change, and what a pull request
needs.

## What ships

One package name, `urim`, on npm (TypeScript, `packages/urim-ts`) and on PyPI (Python, `packages/urim-py`).
Both ports implement the same behavior.

## Setup

CI uses Node.js 24 and Python 3.11 and 3.13, so use those versions. The floors are Node 23.6 (the
TypeScript sources run under Node's type stripping) and Python 3.11.

`scripts/dev` is the everyday entry point (plain bash; `scripts/dev help` lists everything):

```sh
scripts/dev setup        # .venv with every extra (dev, pydantic, httpx) plus ruff, mypy, build; npm ci
scripts/dev test         # both ports' tests; `test py` or `test ts` for one
scripts/dev check        # the one gate below, using .venv
scripts/dev build        # npm dist and Python wheel + sdist into packages/urim-*/dist
scripts/dev pack-check   # install the built packages in a throwaway folder and run an offline example
scripts/dev clean        # remove build outputs (`clean --all` also removes .venv and node_modules)
```

`setup` uses `python3`; set `PYTHON=/path/to/python3.11` to pick another. The `httpx` extra is included,
so the adapter and transport tests run instead of skipping.

## The one gate

```sh
scripts/dev check
# or, to test more than one Python:
PYTHONS=".venv/py3.11/bin/python .venv/py3.13/bin/python" TOOLS=.venv/py3.13/bin bash packages/check.sh
```

This runs pytest under each Python, `ruff check`, `ruff format --check`, `mypy --strict`, the Node test
suite and `tsc --noEmit`. It also checks that nothing under `drafts/` or `research/` is tracked, and runs
the tests for `scripts/dev`. CI (`.github/workflows/ci.yml`) runs the same script.

## Making a change

- **Start with an issue.** For a behavior change, open an issue that describes it before you write code.
- **Tests first.** Write a failing test, then the fix.
- **Both ports, shared fixtures.** Cross-port behavior is pinned by `packages/shared-fixtures/*.vectors.json`,
  which is generated from the TypeScript port (`node --conditions=source test/shared-fixtures.gen.ts` in
  `packages/urim-ts`). If a change affects behavior, regenerate the vectors and make both suites pass in
  the same pull request.
- **camelCase JSON.** Every JSON key Urim writes is camelCase, in both ports. User-chosen map keys
  (question, threshold and tier names) and vendor data are left as they are. A test enforces this.
- **No live calls in tests.** Test adapters against a mocked `fetch` (TypeScript) or a mocked transport
  (Python). Never use real keys.
- **No new runtime dependencies.** Both packages have none. Zod (TypeScript) is an optional peer, and
  pydantic and httpx (Python) are optional extras. Dependencies come only from the npm registry and
  PyPI, and `packages/urim-ts/package-lock.json` is committed.

## Pull request checklist

- [ ] `packages/check.sh` passes locally under Python 3.11 and 3.13.
- [ ] The tests came first, and a fix includes a test that failed without it.
- [ ] If behavior changed in one port, the other port matches and the shared vectors are regenerated.
- [ ] New JSON keys are camelCase.
- [ ] No secrets, `.env` files or live provider calls.
- [ ] The CHANGELOG is updated for user-visible changes.

## License

By submitting a contribution, you license it under the Apache License 2.0, the same license as the project (inbound = outbound, Apache-2.0 §5). No sign-off (`Signed-off-by`) is required.

## Security issues

Don't open a public issue. See [SECURITY.md](SECURITY.md).
