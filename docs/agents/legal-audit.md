# Legal audit: procedure for agents

> Not legal advice. This tells an agent when to run the legal gate and how to read it. The rules themselves are specified in release engineering's AUDIT-LEGAL-GATE-SPEC.md.

## When to run

- After any change to a manifest, a dependency, LICENSE, NOTICE, SECURITY.md, README.md, `docs/` or `config/people.yaml`.
- Always as part of `scripts/verify.sh`. `scripts/verify.sh --release` runs it with `--release`.

```sh
packages/python/.venv/bin/python scripts/audit-legal            # normal run
packages/python/.venv/bin/python scripts/audit-legal --offline  # skips the rules that need PyPI (not with --release: L5-Py FAILs)
packages/python/.venv/bin/python scripts/audit-legal --release  # WARN and every unbuilt rule become FAIL
```

It needs the project venv for PyYAML. The results are also written to `build/legal/audit-legal.json`.

## Reading the result

| Status | Meaning | What you do |
|---|---|---|
| PASS | The rule holds. | Nothing. |
| FAIL | The rule is broken. | Fix it in your change. If the fix is a decision for David (a licence exception, a new mark's owner), stop and report it. |
| WARN | A release-only (*R*) rule is broken. It becomes FAIL with `--release`. | Report it. M3 stays WARN until David's history rewrite (RELEASE-RUNBOOK §3a). That is expected. |
| SKIP | A tool or the network is missing, `--offline` was given, or the rule isn't implemented yet. With `--release`, an unimplemented rule is a FAIL instead ("<rule> not implemented; release mode requires every rule to be built"), L5-Py under `--offline` is a FAIL, a missing tool is `tool missing: …`, and a Python runtime env that can't be built (no PyPI) is `[--release] broken environment: …`; both exit 2. None of these can pass a release. | Say which rules were skipped. A SKIP is never a pass. |

Exit codes: 0 PASS, 1 FAIL, 2 a required tool is missing or the environment is broken (with `--release`, and only when nothing FAILed; the message names each tool and how to install it, or what could not be built). Exit 2 is never a pass.

## Rules implemented today

L1 L2 L4 L5-Rust L5-Py M1 M3 M5 C1 C3 C4 T1 T4 T5. The rest (L3 L5-JS L6 L7 L8 T2 T3 C2 M2 M4) report SKIP "not implemented yet" in a normal run and FAIL with `--release`, so `--release` cannot pass until they are built. Until then, cover them by hand with [docs/legal/RELEASE-CHECKLIST.md](../legal/RELEASE-CHECKLIST.md).

## Things an agent never does here

- Decide a licence exception, a mark's owner, or anything listed as a David decision. Mark it UNVERIFIED or leave a placeholder.
- Add `Signed-off-by`, rewrite history, or publish.
- Edit `spec/`. It is a verbatim copy (`scripts/sync-spec`).
