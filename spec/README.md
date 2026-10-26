# spec/

This is an exact copy of the working draft of the Urim specification, **v0.2.0 draft**, from the upstream decision-contract-spec working tree. `SOURCE.json` records the sha256 of every copied file. `scripts/sync-spec` (run by `scripts/verify.sh`) fails if a copy here differs from that record, or, when the upstream tree is present, if upstream has changed since the last sync. Do not edit these files here. Change them upstream, then run `scripts/sync-spec --write`. A future `site/` will render these files, so a stale copy here becomes a stale site.

- `SPEC.md`: the specification.
- `CHANGELOG.md`: the draft's change history.
- `examples/`: everything in the upstream `examples/` folder: two example contracts, the `urim.lock` lockfile (hoshen 2), the provider descriptor, sample eval rows, and the historical files (`decision.lock.v0.1.0.yaml` and `decision.lock.pre-hoshen.yaml`, the pre-hoshen `dctp:` lockfiles, plus `providers/*.provider.v0.1.0.yaml`). `urim check` fixtures use every one of them as a case (see `fixtures/cases.json`). The old lockfiles are refused with the `dctp:` rename error (C-093), and the provider descriptors are refused as not urim documents (C-060).

**Naming.** The contract key is `urim:`, and the lockfile is `urim.lock` with format key `hoshen`. The old `dctp:` key is refused (CONTRACT.md C-093).

**The example lockfile fails on purpose.** Its hashes, including `integrity`, are all-zero placeholders, so `urim check` reports an integrity mismatch for it (SPEC §6.2). The repo's own sealed lockfiles are in `fixtures/valid/` and `scripts/seal-fixtures` keeps them sealed.

**`model_version`.** The envelope's target field is `model_version` (in every envelope example in this copy), matching the lockfile and David's decision. An earlier draft said `"version"` there; this copy no longer does.

**Not included:** the draft's backups (`backups/`, `SPEC.v0.1.0.md`, `SPEC.pre-hoshen.md` and the old STATUS/CHANGELOG copies), `STATUS.md`, `CONTEXT-HISTORY.md`, `drafts/`, `research/` and `security/`. `CHANGELOG.md` and `SPEC.md` mention some of these files, but they are not in this repo.

The vendor facts in the spec are non-normative and dated. See the note at the end of `SPEC.md`.
