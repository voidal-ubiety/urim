# Changelog

Line numbers refer to the **new** file. The original 0.1.0 line is given in parentheses. Backups of 0.1.0: `SPEC.v0.1.0.md`, `examples/decision.lock.v0.1.0.yaml`, `examples/providers/cloudflare-clef-flash.provider.v0.1.0.yaml`, and `STATUS.v0.1.0.md`. Nothing was renamed, published, pushed, or registered, and no git repo was created.

## v0.2.0-draft (protocol 0.2 merge) — 2026-10-26, ~11:15 ET

Merges the capability (`drafts/SPEC-capabilities.md`), runtime-behavior (`drafts/SPEC-errors-observability.md`) and telemetry (`drafts/SPEC-telemetry-contract.md`) drafts into SPEC.md, under decisions D-9…D-30 (`drafts/DECISIONS.md`). Backups of the pre-merge files are in `backups/`. Nothing was published, pushed, registered or filed.

- **Version key (D-23, David: "let's just use 'urim'"):** contracts and envelopes declare `urim: "0.2"` (§5.1). No other key or alias. The v0.1 key spelling `dctp:` and its protocol name now appear only in history files (this changelog, `SPEC.v0.1.0.md`, `SPEC.pre-hoshen.md`, `STATUS.*.md`, `CONTEXT-HISTORY.md`, backups). In 0.2 a `dctp:` key is `invalid_contract`, and the error names the migration command (§5.10.4).
- **§5.1.2 Typed, closed schemas and absent values (D-12):** every object is closed, every field has one type, and there is no `null`, `undefined` or `any`. Defaults are defined as the meaning of an absent key. Placeholder hashes in the spec and examples are type-valid zeros, so they deliberately fail integrity checks.
- **§5.10 Capability requirements and preferences:** `requires` / `prefers` with explicit fallbacks (`emulate:`, `drop`, `fail`), the migration table (§5.10.4), and credential-driven `selection` (§5.10.6). The §5.10.1 excerpt now matches `examples/incident-triage.decision.yaml`.
- **Examples:** the `dataset_hash: "sha256:REPLACE_WITH_REAL_HASH"` placeholders in both contracts are now type-valid all-zero hashes with a comment (D-12).
- **§6.2 Lockfile:** `hoshen: 2`. Examples: `incident-triage` is 0.2 / 1.3.0, `kyc` is 0.2 / 0.4.0, and `urim.lock` is hoshen 2.
- **Part D — Runtime behavior (new):** D.1 error contract (D.1.1–D.1.6). Per D-19, a schema failure is `response_schema_violation`, a lock mismatch is `lock_violation` (never failover-eligible, never counted by the breaker), and a semantic breach is `nonconformant_response`. D.2 failover and circuit breaking (D.2.1 rule 7: no failover on `lock_violation`). D.3 telemetry, an OpenTelemetry mapping; D.3.6 keeps the mapping at 0.x until the OTel names it uses are Stable, with 1.0.0 only on David's approval, and the spec's 1.0 does not wait on it (D-24, with the #596 quote). D.4 runtime conformance.
- **§7.4 Resolver and CLI flags (new, D-15):** every flag with status and reason, including the planned `--strict-prefers`. README draft: `drafts/README-flags.md`.
- **§8** conformance levels updated; **§11** adds "No endorsement through names"; **§12** marks Q3, Q8 and Q9 resolved and adds Q7 (emulation boundaries); **§13** lists only open items, 1–13, including D-29 (names and packages, OPEN) and the new item 13 (release identity and legal terms).
- **`kind` → `type` (D-18), history:** the rule was "emit both in 0.1; drop `kind` at the next MINOR". Protocol 0.2 is that MINOR, so a 0.2 error object has only `type`, and the dual-emit applies only to tools still emitting 0.1 envelopes (§D.1.4).
- **Security docs (Draft 0.2):** `security/THREAT-MODEL.md`, `security/SUPPLY-CHAIN.md` and `security/LEGAL-NOTES.md` apply the release-engineering legal review after each claim was re-verified. Highlights: `hoshen` is no longer listed as a typosquat (it is ours); nothing assumes the npm `@urim` scope, which exists with an unknown owner; SUPPLY-CHAIN B13 is a verified registry-policy table (§G); new JSR controls (§H); D7 names `saphyr-parser` =0.2.2; B10 tool versions updated; B6 notes that the first crates.io publish needs a token; the PLD dates are added; the G1 ¶ numbers are marked UNVERIFIED; new LEGAL-NOTES §9 licence compliance, §10 marks, §11 contribution terms and §12 David's open decisions.

- **D-31 (`model_version` everywhere, 2026-10-26, ~11:20 ET):** the model version is named `model_version` in the descriptor `models[]` (§4.1), the lockfile target entry (§6.2), and the envelope `target` (§5.7, §D.3.5), matching `fitted_for` and the error object's `target` (§D.1.1). Contract, compiler and descriptor `version`, `urim:` and `hoshen:` are unchanged. Files: SPEC.md, `examples/urim.lock`, `examples/providers/cloudflare-clef-flash.provider.yaml`, `drafts/SPEC-capabilities.md`, `drafts/DECISIONS.md`. Hash impact: lockfile `integrity` and descriptor `hash` change, and so does `resolution.hash` through `descriptor.hash`. The rename is folded into the unreleased `hoshen: 2` with no bump. The example placeholders are unchanged. §13 item 4 keeps only the id-format question.

- **D-32 / D-33 and release identity (2026-10-26, ~11:54 ET):** contribution terms are the DCO (D-32, LEGAL-NOTES §11, with the caveat that it doesn't prevent employer-owned code). Urim ships as one package, `urim`; Thummim and hoshen are internal names, not packages (D-33): THREAT-MODEL A6, T9, #8, #19 and SUPPLY-CHAIN B13 no longer plan `thummim`/`hoshen` claims, and the bare-name watch is optional. Licence Apache-2.0 and contact email `hello@davidthomason.dev` are decided (LEGAL-NOTES §12, SPEC §13 item 13). No examples or hashes change.
- **D-34 and JSR (2026-10-26, ~11:58 ET):** David publishes as an individual for now, with portability to a company org as a requirement (D-34; SUPPLY-CHAIN H6, THREAT-MODEL #28). JSR is decided: scope `@urim` (LEGAL-NOTES §12, SPEC §13 item 13, THREAT-MODEL #26, SUPPLY-CHAIN §H).
- **D-35 (2026-10-26, ~12:00 ET):** the M8 drift pipeline uses Vercel Workflow as a thin, swappable orchestrator around plain, idempotent step functions; state lives in GitHub and the registry; PR review is the gate (non-normative notes in SPEC §4.3 and §10; THREAT-MODEL D9; SUPPLY-CHAIN C10). LangChain/LangGraph are not used for context engineering; a LangChain compile target is recorded as an adoption idea.

### Known conflicts (referenced from SPEC §7.4)

- The reference checker (`/workspace/urim`, `40d4a7f`) still accepts `dctp:`, rejects `hoshen: 2`, and does not know the 0.2 keys. Its copies under `/workspace/urim/spec` are stale. The code worker owns that repo; nothing there was changed.
- *(Resolved by D-31.)* The envelope `target` used `version` while the error object used `model_version`. Both now use `model_version`. The canonical target-id format is still open (SPEC §13 item 4).
- `instructions` is now string-only, and `emulate: split` is declared but not specified (§12 Q7).
- Any key change bumps the hoshen hash.
- The repo links `CONTRIBUTING.md#dependency-policy`, but the file doesn't exist. It should be the DCO version (D-32).
- Every commit now uses `hello@davidthomason.dev`, the decided public email (package metadata still to update).

## Unreleased (Urim YAML profile) — 2026-10-26, ~10:05 ET

Adds the Urim YAML profile to the spec. The reference checker (`urim check`, in JavaScript, Python and Rust) applies it; its contract calls this checker version v0.0.2. The packages are still at 0.0.1. Nothing was published, pushed or registered.

- SPEC.md:141–160 — new §5.1.1 "Urim YAML profile". Contracts and lockfiles are a strict subset of YAML 1.2 (core schema), checked in a fixed order with the first failure reported:
  1. size (1 MiB) and regular file;
  2. profile characters (c-printable, minus NEL, LS, PS and a non-leading U+FEFF);
  3. one well-formed document, no undefined alias, nesting ≤ 64, in stream order;
  4. no anchors, aliases, tags or `<<` merge keys, and no invisible characters in keys;
  5. unique scalar keys, integers in −2^63..2^64−1, core-schema resolution;
  6. schema, where identifiers have no invisible characters.

  Diagnostics escape unsafe characters as `\u{XXXX}`. No other SPEC.md line changed. Every file in `examples/` passes the profile steps (1–5). The two contracts and `urim.lock` also pass `urim check`. The provider descriptors and the 0.1.0 and pre-hoshen lockfile backups are other file kinds, so they stop at the schema step.
- Checker behavior changes (Urim `CONTRACT.md`):
  - A directory now gives `not a regular file` (C-011, C-081). It used to give `cannot read file`.
  - Core tags (`!!str`, `!!int`, …) are refused with `tags are not allowed` (C-085). C-029 is retired.
  - Anchors and aliases are refused (C-084). C-032 is retired.
  - A `<<` key is refused instead of being read as a literal key (C-086). C-033 is retired.
  - NEL, LS, PS and a non-leading byte order mark are `invalid YAML` (C-082).
  - An undefined alias is `invalid YAML`, and so is a syntax error that comes before nesting gets too deep (C-090).
- Cross-language divergences D-001…D-007 and D-010 are resolved by the profile, so all three ports now agree on them. D-008, D-009, D-011 and D-012 remain open for David to decide, and the cross-port scalar corpus found D-013 (empty implicit keys). Since the Rust port moved to saphyr-parser, all three ports agree on D-009 (they accept), but it stays open until David chooses.

## v0.1.1-draft (lockfile rename) — 2026-10-25, ~21:25 ET

Scoped rename approved by David. **Only the lockfile was renamed.** DCTP is not renamed anywhere else, and the CLI verbs stay plain (`plan`, `apply`). Backups: `SPEC.pre-hoshen.md`, `STATUS.pre-hoshen.md`, `CHANGELOG.pre-hoshen.md`, `examples/decision.lock.pre-hoshen.yaml`.

- `examples/decision.lock.yaml` → `examples/urim.lock` (file renamed; line count unchanged, so earlier line refs to this file still hold).
- examples/urim.lock:1 — header comment is now ``# urim.lock (hoshen format). Generated by `urim plan` + `urim apply`; commit it, don't hand-edit.`` The placeholder warning stays at line 2.
- examples/urim.lock:3 — `dctp: "0.1"` → `urim: "0.1"`.
- examples/urim.lock:4 — `lockfile_version: 1` → `hoshen: 1`.
- examples/urim.lock:6 — compiler `{ name: dctp-ref, version: 0.1.0 }` → `{ name: urim, version: 0.1.0 }`.
- SPEC.md:35 — summary table: lockfile (`urim.lock`, hoshen format).
- SPEC.md:237 — envelope example note points to `examples/urim.lock`.
- SPEC.md:299 — §6.2 heading is now "Lockfile (hoshen format)".
- SPEC.md:301 — added "The hoshen is the lockfile format: it holds what was decided and measured, so a verdict can be reproduced." and the file name `urim.lock`.
- SPEC.md:303–311 — new top-level field table (`hoshen`, `urim`, `generated_at`, `compiler`, `contracts`).
- SPEC.md:313 — new `hoshen` compatibility rule: it bumps only on breaking format changes; tools read it first and refuse unsupported values with an error naming both versions; no silent rewrite; upgrades happen only via an explicit `apply`.
- SPEC.md:328 — "See `examples/urim.lock`."
- STATUS.md (11 occurrences) and CHANGELOG.md:59–61 (the v0.1.1 entry below) — references to `decision.lock.yaml` updated to `urim.lock`.
- Not changed: `CONTEXT-HISTORY.md:278` (a historical handoff record, outside scope) and the backup files.
- Parse check: `examples/urim.lock` loads under PyYAML `safe_load` (YAML 1.1) and ruamel.yaml in YAML 1.2 mode. Result: `hoshen: 1` (int), `urim: "0.1"` (str), `compiler: {name: urim, version: 0.1.0}`, `contracts: [incident-triage]`.

## v0.1.1-draft — 2026-10-25 (ET)

### Applied: handoff corrections (CONTEXT-HISTORY.md §7.2), each re-checked against sources

| # | Change | Where |
|---|---|---|
| 1 | Perplexity Decider and Inception Mercury Decide moved to the `systemone` camp (systemone body shape served at a `/v1/decisions` path). The `decisions` camp is now OpenAI only, with LiteLLM and OpenRouter as gateway routes. M1's `decisions` target is OpenAI. Microsoft Decision-1's wire shape marked UNVERIFIED. Liquid and Fastino paths added. | SPEC.md:41–44 (41–42); SPEC.md:390 (379) |
| 2 | Vendor examples for experimental types: Jev `box` (opt-in header) and Inception `extract` (1–26 fields, returns spans). | SPEC.md:154–155 (152–153) |
| 3 | Score semantics note: Jev, Clef and Inception return the expected level, while GLiDE returns the argmax and reports `expected_level` separately. The envelope `expected_level` is computed from `distribution`. | SPEC.md:240 (229) |
| 4 | Registered `normalized_top` (Jev, Perplexity) and `abs_2p_minus_1` (GLiDE noul). Added a non-normative paragraph on native definitions, including the Jev and Perplexity score-spread formulas (not registered; naming is OPEN-DECISION) and which vendors return yes/no confidence. | SPEC.md:178–181 (after 173) |
| 5 | sys1bench version 0.3.1 → 0.3.2. | SPEC.md:380 (369) |
| 7 | Jev context conflict (TypeSafe 64k/32k vs Vercel 32K) added as a second source-conflict example. | SPEC.md:95 (93) |

### Rejected

| # | Proposed | Reason |
|---|---|---|
| 6 | "Jev image claim can't be re-found; Jev is text-only" | Conflicts with a verified primary source. docs.typesafe.ai/images documents experimental image input and `box`, enabled with the header `TypeSafe-Danger-Zone-Images: true`, while docs.typesafe.ai/models says "Input: Text". The conflict is real, so the example was kept and both URLs added (SPEC.md:95). |

### Applied: unambiguous audit fixes (STATUS.v0.1.0.md)

- SPEC.md:1, 5 — version label 0.1 → 0.1.1 draft. The project name is unchanged (TBD).
- SPEC.md:17 — "at least three ways" of computing confidence → "at least four documented ways (§5.4)".
- SPEC.md:43 — Vercel `/v1/evaluate` noted as its own vocabulary (`boolean`), treated as an adapter.
- SPEC.md:57 (55) — the Clef "squared top-two gap" rationale marked UNSOURCED. The principle itself stands.
- SPEC.md:78 (76) — `min_choice_options` added to descriptor `limits`.
- SPEC.md:88 (86) — OpenAI limits added (2–255 choices, 2–10 levels). LiteLLM 1–128 marked not confirmed. Hosted Clef-flash endpoint documented, with a note that `/v1/systemone` is self-hosted only. Pinning hosted Clef marked UNVERIFIED.
- SPEC.md:95 (93) — primary-source URLs for the Jev image conflict.
- SPEC.md:165 (new) and SPEC.md:192 (184) — compile-time rejection of a `choice` below the target's `min_choice_options` (e.g. one-option choices on OpenAI and Workers AI).
- SPEC.md:175 (171) — `margin_squared` no longer attributed to Clef (UNSOURCED).
- SPEC.md:197 (189) — jevcompat 0.768→0.351 figure marked UNVERIFIED.
- SPEC.md:203 (195) — Vercel `/v1/evaluate` yes/no type named `boolean`.
- SPEC.md:218, 225, 227, 230 (210, 217, 219, 222) — envelope example made consistent with the lockfile: provider `cloudflare`, `native: null` (Clef gives no noul confidence), threshold 0.71 → 0.78, cost 0.00012 `per_token` `estimated: true`.
- SPEC.md:237–238 (new) — example notes (version PLACEHOLDER) and a rule that `confidence.native` MUST be null when the provider returns none.
- examples/urim.lock:20 — Jev version "2026-09-15" → `"jev-1.14.0"  # PLACEHOLDER` (semver format, as in jev-1.13.0).
- examples/urim.lock:39 — Clef version marked PLACEHOLDER (Workers AI has no versioned id).
- examples/urim.lock:50–51 — comment no longer asserts Clef's formula (UNSOURCED).
- examples/providers/cloudflare-clef-flash.provider.yaml:10–13 — hosted Workers AI endpoint note, with source URL.
- examples/providers/cloudflare-clef-flash.provider.yaml:26–28 — `confidence.definition: margin_squared` → `undocumented`, source set to the Cloudflare model page, marked UNSOURCED.

### OPEN-DECISION notes added (not decided)

- SPEC.md:44 — camp definition rule.
- SPEC.md:162 — box/experimental fallback (§5.3 vs §5.9).
- SPEC.md:181 — score-spread definition naming.
- SPEC.md:237 — canonical target-id format.
- SPEC.md:395 — M2 lock-before-plan vs principle 5.
- SPEC.md:421–435 — new §13 listing all reserved decisions (grammars, hash canonicalization, naming, `applies_to: portable`, yes/no threshold direction).
