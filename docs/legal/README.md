# docs/legal

> Not legal advice. These files record the project's own licensing and naming choices and the checks that enforce them.

| File | What it is | Checked by |
|---|---|---|
| [license-policy.yaml](license-policy.yaml) | Allowed, review and denied licences for shipped dependencies. `packages/rust/deny.toml` mirrors it. | `scripts/audit-legal` L5 |
| [marks.yaml](marks.yaml) | Third-party marks the docs name, with owner and allowed use. Owners marked UNVERIFIED are unconfirmed. | `scripts/audit-legal` T1, T4 |
| [DCO-1.1.txt](DCO-1.1.txt) | The Developer Certificate of Origin 1.1, verbatim. | `scripts/check-dco` |
| [RELEASE-CHECKLIST.md](RELEASE-CHECKLIST.md) | What a person checks before each publish. | (people) |

The procedure for agents is [docs/agents/legal-audit.md](../agents/legal-audit.md). The project licence is Apache-2.0 ([LICENSE](../../LICENSE), [NOTICE](../../NOTICE)).
