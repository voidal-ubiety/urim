# AGENTS.md: guide for coding agents (and humans) working on Urim

Urim is an open-source decision-model client library: you define a decision in code, Urim calls a
chain of model tiers, applies confidence cutoffs, and returns a typed result plus a portable `urim/1`
envelope. Two ports ship with the same behavior: TypeScript (`packages/urim-ts`, npm `urim`) and
Python (`packages/urim-py`, PyPI `urim`). License: Apache-2.0.

Tool notes: Codex and Cursor read this file directly. `CLAUDE.md` imports it for Claude Code.
Keep the rules here and nowhere else, so they don't drift.

## Code map
| Path | What |
|---|---|
| `packages/urim-ts/src` | TypeScript port (`client.ts`, `cli.ts`, `camps/` provider adapters, `adapters/`). |
| `packages/urim-py/src/urim` | Python port. `boundary.py` is the only place snake_case Python names map to camelCase JSON. |
| `packages/shared-fixtures/*.vectors.json` | Cross-port vectors, generated from the TS port. |
| `packages/check.sh` | The one gate (tests, lint, types, both ports). CI runs it. |
| `.github/workflows/ci.yml`, `publish.yml` | CI, and publish on `v*` tags. |

## Setup and checks (exact commands)
```sh
(cd packages/urim-ts && npm ci --ignore-scripts)
for v in 3.11 3.13; do
  uv venv --python "$v" ".venv/py$v"
  uv pip install --python ".venv/py$v/bin/python" -e "packages/urim-py[dev,pydantic,httpx]" ruff mypy
done
PYTHONS=".venv/py3.11/bin/python .venv/py3.13/bin/python" TOOLS=.venv/py3.13/bin bash packages/check.sh
```
Regenerate shared vectors after a behavior change: `cd packages/urim-ts && node --conditions=source test/shared-fixtures.gen.ts`.
Done means `packages/check.sh` ends with `== all checks passed`.

## Conventions
- **Test first, one slice at a time.** A failing test, then the fix, then the full gate.
- **Both ports, same PR.** Behavior changes land in TS and Python together, with vectors regenerated.
- **JSON keys are camelCase** everywhere Urim writes JSON. **Enum values are snake_case** (e.g. `provider_unavailable`, `rate_limited`). User-chosen map keys and vendor data stay as given.
- **Python API is snake_case**, mapped to JSON only through `boundary.py`.
- **No live provider calls in tests.** Mock `fetch` (TS) or the transport (Python). Never use real keys.
- **No new runtime dependencies.** Zod, pydantic and httpx stay optional.
- **Commits:** small, imperative subject, scoped (`feat(client): ...`). No `Signed-off-by` (no DCO; Apache-2.0 §5 inbound = outbound).

## Rules for agents
- Never print, echo, commit or log tokens, API keys or other secrets.
- Never invent facts, vendor behavior, prices or limits. Cite a source (path, command output, URL) or write **UNVERIFIED**.
- Don't push to `main`, publish packages, or contact anyone unless the maintainer explicitly asked for that action.
- Changes reach `main` only through pull requests.
- Security issues: see `SECURITY.md`, not a public issue.

## Working style
State the definition of done, your assumptions and your confidence. Mark unknowns. Keep reports short.
Before reporting done: re-read the task, run the gate, re-read your diff for scope. At most 3 fix-and-recheck passes, then report what's still open.

## Maintainers
In the maintainers' source checkout, more agent docs live under `docs/agents/` (absent from the public
repo). If `docs/agents/INTERNAL.md` exists, read it before doing anything else; its rules take priority.
