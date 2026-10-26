# spec/

This is a copy of the working draft of the Urim specification (v0.1 draft, with the v0.1.1-draft edits). It was taken on 2026-10-25.

- `SPEC.md`: the specification.
- `CHANGELOG.md`: the draft's change history.
- `examples/`: example contracts, the `urim.lock` lockfile (hoshen format 1), a provider descriptor, and sample eval rows. The `urim check` fixtures also use the contracts and the lockfile as valid cases.

**Naming is mid-transition.** Only the lockfile has been renamed so far: it is `urim.lock`, format key `hoshen`. The contract format is still called **DCTP** in the spec text, and contracts still use the `dctp:` key. That is deliberate. The DCTP → Urim rename is still an open decision, so the text is unchanged here. `urim check` accepts either `dctp:` or `urim:` as the contract version key.

**Not included:** the draft's backup files (`*.v0.1.0.*`, `*.pre-hoshen.*`), `STATUS.md`, `CONTEXT-HISTORY.md`, and research notes. `CHANGELOG.md` mentions these files and gives line references for them. The files themselves are not in this repo.

The vendor facts in the spec are non-normative and dated. See the note at the end of `SPEC.md`.
