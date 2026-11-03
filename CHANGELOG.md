# Changelog

Release notes for the `urim` packages: `urim` on npm (TypeScript, `packages/urim-ts`) and `urim` on PyPI (Python, `packages/urim-py`). Both share one version.

## 0.0.1 (Unreleased)

Nothing has been published yet. This is the first release of the v1 client; the v0.2 `urim check` tool was never published and is not part of it.

### Added
- `defineDecision` in code: tiers, input schema (Zod in TypeScript, optional peer; pydantic v2 in Python, optional extra), questions (`noul`, `choice`, `score`), failover rules and named thresholds.
- `urim emit`: canonical JSON of each decision plus its hash.
- `urim fit`: per-tier cutoffs from labelled cases into `urim.lock`; stops at a cost estimate unless `--yes` is passed.
- `urim providers`: generates the frozen provider constants from a registry file.
- `urim.lock`, required only in prod mode, where the decision hash must match.
- Tiered fallback with a pre-call budget skip (input estimated from the UTF-8 byte length of the request body).
- `confidenceSource` on every answer: `native`, `urim_derived` or `null`.
- `confidenceFormula` on every answer: `systemone_normalized` (Urim's |2p − 1| for yes/no, the `systemone` request format's normalized formula), `vendor_unspecified` (the vendor's own number) or `null`. Optional for readers, so older urim/1 envelopes still read.
- The definition's `confidence` now names those formulas per question type, `{ noul: "systemone_normalized", choice: "vendor_unspecified", score: "vendor_unspecified" }`, replacing `"top_probability"`, which did not describe what Urim computes. Urim sets it; `defineDecision` no longer needs it.
- **Contract hashes changed.** The `confidence` member is hashed, so every contract hash differs from pre-release builds (the triage example went from `sha256:202296be…` to `sha256:7abe2a44…`). Re-run `urim emit` and `urim fit` for any lock written before 0.0.1.
- Descriptor flag `confidenceUnavailableSentinel` (Python `confidence_unavailable_sentinel`): for a provider that sends `confidence: 0` with empty `probabilities` to mean "unavailable", those answers decode as confidence `null`, so cuts escalate them and `fit` does not count them as a real 0. No shipped descriptor sets it.
- `deadlineMs` (Python `deadline_ms`) is a hard stop: once its timer fires, the deadline counts as spent even if the measured clock still reads a little under it. The current tier records `timeout`, and every later tier records `timeout` without a call. Before this fix a timer that fired early could let the next tier run. A timeout error reported by an adapter does not spend the deadline. The budget skip is still cost-only, and there is no deadline skip.
- `createClient({ deadlineMs })` (Python `create_client(deadline_ms=...)`): a client-wide default total deadline, unset by default. It must be a finite number > 0, otherwise creation fails with `invalid_definition`. A per-call `deadlineMs` overrides it, and `null` (Python `None`) opts out for that call. `explain()` includes the effective `deadlineMs` when there is one. Per-tier time limits are deferred to v1.x.
- Typed errors: one `UrimError` with a closed set of types.
- Two opt-in HTTP adapters, one per request format (`systemone`, and `decisions` via `openaiDecisions`), in `urim/adapters` (TypeScript) and `urim.adapters` (Python). Tested against mocked HTTP only; no live provider call has been made.
- Descriptors (wire format, URL, auth) for eight providers.
- Renamed the yes/no `confidenceFormula` value to `systemone_normalized`, after the request format it comes from. It changes every contract hash again; re-run `urim emit` and `urim fit`.
- `urim --help`, `urim -h`, `urim help` and `urim <command> --help` print usage to stdout and exit 0. A usage error still prints usage to stderr and exits 1.

### Known limits
- No measured accuracy, latency or cost numbers yet.
- `urim fit` runs against a fake provider file (`--fake`), not a live provider.
