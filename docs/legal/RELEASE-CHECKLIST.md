# Release checklist (legal)

> Not legal advice. A person works through this list before **every** publish to npm, PyPI, crates.io or JSR. It is derived from release engineering's LEGAL-CHECKLIST-v0.0.1 §1 (items A1–A11). Every publish is effectively irreversible.

Run first: `scripts/verify.sh --release`. It runs `scripts/audit-legal --release` and `scripts/check-dco`. In `--release`, every audit-legal rule that is not built yet (the "not automated yet" ones below) is a FAIL, so the gate stays red until they are built; checking them by hand does not turn it green. Run it online: with `--release`, `--offline` FAILs L5-Py, and no access to PyPI is a broken environment (exit 2). Each line below names the gate rule that covers it, if one does.

- [ ] **A1 Licence.** `license` is `Apache-2.0` in package.json, pyproject.toml, Cargo.toml and jsr.json (gate L2). LICENSE and NOTICE are in every artifact (L1; L3 is not automated yet, so inspect the dry-run file lists).
- [ ] **A2 Dependency licences.** Every shipped runtime dependency satisfies [license-policy.yaml](license-policy.yaml) (L5-Rust, L5-Py; L5-JS is not automated yet).
- [ ] **A3 Email and history.** No placeholder email remains in files or in git history (M3). The history rewrite is RELEASE-RUNBOOK §3a and only David runs it, before the first push. Every commit then carries a human `Signed-off-by` (check-dco).
- [ ] **A4 Dry runs.** Read the file lists from `npm pack --dry-run`, `python -m build` plus `twine check --strict`, `cargo package --list` and `npx jsr publish --dry-run`. Look for secrets, personal data and stray files.
- [ ] **A5 One package.** Exactly one package per registry, named `urim` (`@urim/urim` on JSR). No placeholder packages, and no thummim or hoshen names.
- [ ] **A6 npm scope.** No doc or install command uses `@urim/...` on npm.
- [ ] **A7 JSR.** `packages/js/jsr.json` is `@urim/urim` at the same version as package.json (check-project).
- [ ] **A8 Marks.** Every third-party mark used is in [marks.yaml](marks.yaml) (T1), with no mark in a package name (T4). Confirm each UNVERIFIED owner. Read the docs for endorsement wording by hand (T2 and T3 are not automated yet). The README keeps the line "Jev is a product of TypeSafe" (T5).
- [ ] **A9 SECURITY.md.** It exists, gives a reporting channel and makes no fix-time promises (C4). The README links to it.
- [ ] **A10 No monetisation surface.** No funding tiers or promise wording (C1), and no network imports in shipped code (C3).
- [ ] **A11 `model_version`.** The variant scan in RELEASE-RUNBOOK §2 prints nothing (docs/adr/0001).
