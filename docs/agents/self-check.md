# Agent self-check (D-30)

Every agent working on Urim runs this check before it reports a task done. Source: decision D-30 in the spec repo's `drafts/DECISIONS.md` (accepted 2026-10-26). The self-check does **not** replace architect review.

## The check

1. Re-read the task's definition of done.
2. Every factual claim in the deliverable and the report is sourced (a repo path, a command and its output, or a URL), or marked **UNVERIFIED**. Never fill a gap with a guess about a vendor, a registry or a standard.
3. Every cited ID, section, path and URL exists. In this repo:
   - contract IDs (`C-0xx`) and divergences (`D-0xx`): `python3 scripts/contract-check.py`
   - legal links and the marks list: `packages/python/.venv/bin/python scripts/audit-legal --offline` (rules M5, T1)
4. Re-run the task's verification. For code, run the full `scripts/verify.sh` (about 3 minutes; run it in the background). Before a release, also run `scripts/verify.sh --release`.
5. Re-read the diff (`git diff`, `git status`) for:
   - **Scope.** Nothing outside the task. Generated files are regenerated, not hand-edited (`spec/`, `.github/CODEOWNERS`, the schema files).
   - **Type holes.** Undefined values, untyped keys, nullable members that aren't declared as nullable.
   - **Parity.** A change to one port is matched in the other two. Coverage stays at 100%.

If any step finds an issue, fix it and run the **whole** check again. Stop when a pass finds zero new findings. The hard cap is **3 passes**. If pass 3 still finds issues, stop and report the task as **blocked** to the Architecture Agent, listing what remains.

## Never, as an agent

- Add `Signed-off-by` (CONTRIBUTING.md "Commits written by an agent").
- Push, publish, reserve a name or contact anyone without David's explicit yes.
- Change behaviour silently. A real bug needs a failing-then-passing test and its own commit. A conformance gap that you don't fix is pinned as a `D-0xx` divergence (CONTRACT.md §D).

## The `self_check` record

Every report ends with a `self_check` record. Its shape is [`review-findings.schema.json`](review-findings.schema.json):

```json
{
  "self_check": {
    "passes": 2,
    "findings_per_pass": [3, 0],
    "fixes": ["M5: CONTRIBUTING linked a missing file; created it"],
    "unverified": ["owner of the LiteLLM mark"],
    "status": "done"
  }
}
```

`status` is `done` when the last pass found nothing. It is `blocked` when pass 3 still found issues.
