# 0001. `model_version` everywhere (D-31)

- **Status:** Accepted, 2026-10-26.
- **Decided by:** David (D-31, about 11:20 ET). Source: the spec working tree's `drafts/DECISIONS.md` (D-31 row) and `CHANGELOG.md` (v0.2.0-draft), and SPEC.md §6.2 and §13 item 4 in [`spec/SPEC.md`](../../spec/SPEC.md).

## Context

Before v0.2.0-draft the envelope `target` called the pinned model version `version`, while the error object and `fitted_for` called it `model_version`. A bare `version` already means the contract, compiler or descriptor semver.

## Decision

The pinned model version is named `model_version` everywhere: descriptor `models[]`, the lockfile target entry, `fitted_for`, the envelope `target` and the error object `target`. A bare `version` stays the contract, compiler or descriptor semver. `urim:` and `hoshen:` are unchanged. The rename is folded into the unreleased `hoshen: 2`, so there is no format bump.

## How this repo applies it

- `schema/urim-0.2.json` (and the generated `schema.gen.ts`, `schema_gen.py` and `schema_gen.rs`) defines `model_version` on lockfile targets and in `fitted_for`. No `version` alias exists. A target with `version` is refused as an unknown key (CONTRACT.md C-095).
- All three ports and every fixture use `model_version`.
- Lockfile `integrity` covers the field name, so a lockfile that used the old name cannot pass by renaming the field without resealing.

## Not decided here

The canonical target-id format (`provider` + `model` vs a single `vendor/model`) is still open (SPEC §13 item 4).
