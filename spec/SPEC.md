# Urim — decision contract protocol — v0.2.0 draft

| | |
|---|---|
| Status | Working draft 0.2.0 (merges the capability, runtime-behavior and telemetry drafts of 2026-10-26 into 0.1.1; see CHANGELOG.md). Unpublished. Not a claim of adoption or vendor endorsement. |
| Author | David Thomason (github.com/no-complect) |
| Reference implementation | Jev Harness (https://www.jev-harness.dev), an independent demo built on TypeSafe's Jev |
| Name | **Urim** is the protocol and its compiler/reference tool; **Thummim** is the eval suite used by `plan`; **hoshen** is the lockfile format (`urim.lock`). Urim ships as **one package, `urim`, on every registry**. Thummim and hoshen are internal names that ship inside it, not packages (D-33). Docs give only the `urim` install commands. The `urim` names and domains are not claimed yet (§13 item 6). |
| Version key | Contracts and envelopes declare `urim: "0.2"` (§5.1). There is no other version key and no alias. |
| Date | 2026-10-26 |

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC 2119] [RFC 8174] when, and only when, they appear in all capitals, as shown here.

Conventions: `PROPOSED` marks a key or name that is specified here but whose spelling is not final (§13). `TODO(vendor-fact)` marks a vendor field, header, limit or number this draft deliberately does not invent. YAML and lockfile values in examples are illustrative placeholders.

---

## 1. Summary

Decision models ("System 1" models) take application state plus typed questions and return typed answers with probabilities instead of generated text. As of October 2026, at least eight vendors ship one, in **two incompatible API styles** with **at least four documented ways of calculating `confidence`** (§5.4). Applications that hard-code one provider's request shape and one model's threshold have to be rewritten when prices change, a provider shuts down, or a better model ships.

Urim describes a decision **once**, in a provider-neutral **contract** file, and:

1. **compiles** it to any supported provider's native request (or to an existing adapter such as the Vercel AI SDK), and normalizes the response into one envelope;
2. **locks** the exact provider, model version, capability resolution, and *per-model fitted thresholds* in a lockfile;
3. **plans** any provider or model change by running the contract's bound eval set and refusing the switch if the new target does not meet the contract's acceptance criteria.

Changing providers then means a config change plus a passing `plan`, not a rewrite.

Design lineage: **Terraform** (declarative config + pluggable providers + `plan`/lock) and **TypeScript** (ship ahead of the standard; adopt one call at a time; compile down to whatever targets actually support).

The protocol has four parts:

| Part | Problem | Artifact |
|---|---|---|
| A. Provider registry | Data mining: what can each provider do, and at what cost? | Provider capability descriptor (`*.provider.yaml`) |
| B. Contract and transpilation | Isomorphic interface handling: one contract, many wire formats | Contract (`*.decision.yaml`), response envelope |
| C. Versioning | Version control: what changed, and is it still safe? | Contract semver, lockfile (`urim.lock`, hoshen format), `plan` report |
| D. Runtime behavior | What happens when a call fails, fails over, or is observed | Error contract, failover rules, telemetry mapping |

## 2. Terminology

- **Urim type** — one of the provider-neutral question types of §5.3 (`choice`, `score`, `yesno`, and the experimental `box`, `extract`).
- **Decision model / provider** — a service or open-weight model that scores a supplied answer space and returns typed answers without generating them token by token.
- **Camp** — a family of wire formats. v0.2 recognizes two:
  - **`systemone` camp** — TypeSafe's `POST /v1/systemone` body shape (`model`, `state`, `questions` as a map; question types `choice`, `score`, `noul`; choice options in `criteria`). Also used by Cloudflare Clef/Clef-flash, Liquid AI d1 (`/decisions/v1/systemone`), Fastino GLiDE, and many open "Jev-compatible" servers. **Perplexity Decider and Inception Mercury Decide also use this body shape even though they serve it at a `/v1/decisions` path** (docs.perplexity.ai/docs/decisions/quickstart; docs.inceptionlabs.ai/capabilities/decisions, checked 2026-10-25). Microsoft Decision-1 (Foundry) is listed here provisionally; its wire shape is UNVERIFIED. Formalized by DMP draft 0.1.
  - **`decisions` camp** — OpenAI's `POST /v1/decisions` body shape (`model`, `input`/`input_json`, `questions` as an **array** of items with `name`; question types `predicate`, `choice` with `choices[{value,description}]`, `score` with `levels[{label,description}]`; response `answers[]`). As of 2026-10-25 only OpenAI (also on Azure) ships this shape natively; LiteLLM and OpenRouter expose it as gateway routes.
  - Vercel AI Gateway `/v1/evaluate` uses its own vocabulary (yes/no type named `boolean`) and is treated as an adapter target (§5.6).
  - > **OPEN-DECISION (David): camp definition rule** (§13 item 1). The prose above classifies by body vocabulary. Whether the spec should formally define camps by body vocabulary, by path, or add a third `gateway`/`evaluate` camp is not decided.
- **Contract** — a versioned, provider-neutral declaration of state inputs, questions, answer spaces, capability requirements, policy, and eval binding.
- **Target** — a concrete (provider, model, endpoint or adapter) to which a contract compiles.
- **Native confidence** — whatever number the provider returns as `confidence`, with the provider's own definition.
- **Portable confidence** — a confidence value Urim computes from the returned distribution, using a definition named in the contract (§5.4).
- **Policy** — thresholds and actions that turn probabilities into application behavior. Policy lives in the contract and lockfile, never in the model request.
- **Eval set** — labeled cases bound to a contract and used by `plan` (run by Thummim).
- **Resolution** — the per-target outcome of the capability resolver (§5.9, §5.10), recorded in the lockfile and executed, never recomputed, by a runtime.
- **Runtime** — whatever executes a compiled, locked call: a future Urim runtime, Jev Harness, a generated client (§5.8), or an adapter integration (§5.6). Part D applies to all of them.

## 3. Design principles

1. **Contract first, wire format second.** The contract is the source of truth. Wire formats are compile outputs.
2. **Complement, don't replace.** Existing adapters are valid compile targets (§5.6). Urim adds the contract, lock, and plan layers they lack.
3. **Never silently re-mean a number.** Native values MUST be preserved verbatim. Anything Urim derives is labeled as derived, with its definition.
4. **Thresholds are per model, not per contract.** A threshold fitted on one model MUST NOT be assumed valid on another. (Observed: a 0.9 cutoff tuned on Jev kept none of Clef's answers on one test, attributed in 0.1.0 to Clef's confidence being the squared top-two gap. That formula is UNSOURCED (§5.4), but the observation does not depend on it: native confidence definitions differ across vendors either way.)
5. **Switching is gated by evidence.** No target enters a lockfile without a passing `plan` against the contract's eval set.
6. **Incremental adoption.** One call site can adopt Urim without touching the rest of the application.
7. **Contributable upstream.** Where Urim overlaps the Decision Model Protocol (DMP) or the OpenTelemetry GenAI conventions, it SHOULD adopt their definitions and offer its additions back (§9). Nothing is filed upstream without David's explicit approval per item.
8. **Nothing is undefined.** Every contract and lockfile key has a declared type, unknown keys are errors, and every optional key has a written meaning when absent (§5.1.2).

---

## 4. Part A — Provider registry (data mining)

### 4.1 Capability descriptor

Each target is described by a machine-readable **provider capability descriptor**. A compiler MUST consult the descriptor before emitting a request, and MUST fail at compile time (not at call time) if a contract uses a capability the target lacks, unless the target was excluded by `requires` (§5.10.2) or the contract declares that feature in `prefers` with a fallback (§5.10.3).

Required fields:

| Field | Meaning |
|---|---|
| `id`, `vendor`, `models[]` | Stable identifiers; each model entry has a pinned `model_version` and optional alias (e.g. `jev-latest`). |
| `camp` | `systemone` \| `decisions` \| `adapter` |
| `endpoint` | Base URL and path template; auth scheme (API key, Entra ID, etc.). |
| `question_types` | Map from Urim type to native name, e.g. `yesno: noul` (systemone) or `yesno: predicate` (decisions). Unsupported types are omitted. |
| `limits` | `max_questions_per_request`, `min_choice_options`, `max_choice_options`, `score_levels {min,max}`, `max_state_bytes`. |
| `modalities` | `text`, `json`, `image`, `audio`, `video`; each with `status: ga \| experimental` and any required opt-in header. |
| `confidence` | `definition` (one of the registered names in §5.4, or `undocumented`), plus `source` URL. |
| `pricing` | `basis` (`per_request` \| `per_question` \| `per_token` \| `self_hosted`), `unit_price`, `currency`, `as_of`. |
| `residency` | Regions, private networking, data retention statements. |
| `features` | `caching.prompt`, `refusal.typed`, other optional features, each with `status`. |
| `descriptor_version` | Semver of the descriptor itself (§4.2). |
| `weights` | For open-weight models: `license` (SPDX id), `commercial_restrictions` (free text, e.g. revenue caps), `vram_gb_estimate`. |
| `provenance` | For every field group: `source_url`, `retrieved_at`, `method` (`docs` \| `openapi` \| `probe` \| `vendor_submitted`). |

Optional field groups (PROPOSED; schemas TODO, values only with provenance through §4.3):

| Field | Meaning |
|---|---|
| `errors` | How the provider's failures map to the error `type` of §D.1.2: the request-id location, retry-hint headers, and the vendor signals that distinguish e.g. `quota_exceeded` from `rate_limited` (§D.1.6). |
| `extensions` | One JSON Schema (2020-12, closed) plus an effect class (`transport` \| `behavioral`) for every `x-<provider>` extension key the provider accepts (§5.11.3). |

Absent `errors` means the generic HTTP column of §D.1.2 applies. Absent `extensions` means the provider accepts no `x-<provider>` extension; any such key in a contract is then `invalid_contract`.

Example values observed on 2026-10-25 (non-normative; see `examples/providers/`): OpenAI Decisions accepts up to 400 questions per request, 2–255 choices, and 2–10 score levels; Clef accepts 1–64 questions; LiteLLM's OpenAI decisions route is reported to accept 1–128 (not confirmed on the LiteLLM docs page as fetched). Hosted Clef-flash is called at `POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/clef-flash` (Bearer token; the answer body is wrapped in a `result` object). `/v1/systemone` applies only when the open weights are self-hosted. Workers AI exposes no versioned model id, so whether hosted Clef-flash can be version-pinned is UNVERIFIED (see §12 Q9). Liquid d1 and Fastino GLiDE open weights restrict production use by companies above a revenue threshold; Clef, Clef-flash, Clef-omni, Perplexity Decider v1.2/Decider-flash, and Fastino GLiNER2.5-Decide are listed as Apache-2.0.

### 4.2 Sourcing and freshness

Descriptors are data, kept in a public registry repository and versioned independently of the spec.

- Every field group MUST carry `provenance`. Fields without provenance MUST be treated as `unknown`.
- When official sources disagree, the descriptor MUST record both sources and SHOULD apply the robustness rule from jevcompat: *declare only what every official client can rely on; mark the rest `experimental`*. Examples observed on 2026-10-25: (a) docs.typesafe.ai/models lists Jev input as text-only, while docs.typesafe.ai/images documents image input and the `box` type, both experimental and enabled per request with the header `TypeSafe-Danger-Zone-Images: true`; (b) TypeSafe documents Jev context as 64k per request / 32k per question, while the Vercel AI Gateway model page lists 32K.
- A descriptor older than its `max_age` (default 30 days) MUST produce a warning on `plan`; pricing older than `max_age` MUST be labeled "estimate" in cost reports.
- `method: probe` entries are produced by an automated capability probe (limits, type support, response conformance). Probes MUST respect provider terms of service; probes that send malformed input MUST NOT be run against hosted APIs whose terms prohibit it.
- Where a provider supports DMP-style capability discovery, the registry SHOULD prefer it over scraped docs once it exists.
- Each descriptor carries its own semver (`descriptor_version`). Removing or narrowing a capability is MAJOR; adding one is MINOR; correcting provenance or pricing is PATCH. Lockfile capability constraints (§6.2) are expressed against these versions.

### 4.3 Registry maintenance pipeline

Descriptors go stale as vendors ship. The registry is kept current by an automated, human-gated pipeline:

1. **Watch.** A scheduled watcher fetches each provider's sources listed in `provenance` (docs pages, OpenAPI files, changelogs, model cards, license files, pricing pages) and, where permitted, runs capability probes. It normalizes each source into the descriptor's field groups.
2. **Detect drift.** It diffs the normalized result against the current descriptor. A **drift** is any field-group difference, classified as `capability_added`, `capability_removed`, `limit_changed`, `confidence_definition_changed`, `pricing_changed`, `license_changed`, `model_version_added`/`deprecated`, or `source_conflict` (official sources disagree). Cosmetic page changes that leave normalized fields unchanged MUST NOT count as drift.
3. **Open an issue.** Each drift opens exactly one issue on the configured task board (GitHub Issues or Linear), deduplicated by (provider, field group, observed value). The issue MUST include the field, old and new values, source URLs, retrieval timestamps, and the affected contracts and lockfile entries in known public consumers.
4. **Draft a PR.** An agent drafts a pull request that updates the descriptor, including its `errors` and `extensions` groups (with new provenance and a `descriptor_version` bump per §4.2), updates the resolver adapter for that target if needed (§5.9), and adds or updates conformance fixtures that exercise the changed capability (a test that passes on the new behavior and fails on the old).
5. **Gate.** The PR MAY merge only when (a) the Urim conformance suite passes against recorded fixtures and, where allowed, the live target; (b) the calibration regression suite on a public reference eval set shows no unexplained change beyond tolerance for affected models; and (c) at least one human maintainer approves. Descriptor changes MUST NOT be auto-merged. `capability_removed`, `confidence_definition_changed`, and `license_changed` MUST require two maintainer approvals.
6. **Notify consumers.** On merge, the release notes list the drift class, so `plan` in downstream projects can warn when a locked target's descriptor moved outside the lockfile's capability constraints.

The pipeline MUST NOT contact vendors, post publicly outside the registry's own repository and board, or run probes that a provider's terms prohibit.

*Implementation note (non-normative, D-35):* this section does not prescribe an orchestrator. Urim's own registry runs the steps above as plain, idempotent functions under a thin orchestrator wrapper (Vercel Workflow for now, swappable), keeps pipeline state in GitHub Issues, pull requests and the registry, and uses GitHub PR review as the human gate (`drafts/DECISIONS.md` D-35).

---

## 5. Part B — Contract and transpilation (isomorphic interface handling)

### 5.1 Contract file

A contract is a file in the Urim YAML profile (§5.1.1) or the equivalent JSON, validated by a published, closed JSON Schema (2020-12) under the rules of §5.1.2. Top-level keys (the full type table is §5.1.2):

```yaml
urim: "0.2"                 # protocol version, REQUIRED
contract: incident-triage   # id, REQUIRED, kebab-case
version: 1.3.0              # contract semver, REQUIRED (§6.1)
description: ...            # OPTIONAL
state:                      # typed inputs, REQUIRED (§5.2)
questions:                  # REQUIRED, ordered map, >= 1 (§5.3)
policy:                     # thresholds + actions, OPTIONAL but RECOMMENDED
confidence:                 # portable confidence definition, OPTIONAL (§5.4)
eval:                       # eval binding + acceptance criteria, REQUIRED for `plan` (§7.1)
targets:                    # explicit candidate targets, OPTIONAL (the lockfile decides what is live)
targets_query:              # browserslist-style target selection, OPTIONAL (§5.9)
requires:                   # hard capability requirements, OPTIONAL (§5.10.2)
prefers:                    # soft capability preferences with declared fallbacks, OPTIONAL (§5.10.3)
accept_lock_in:             # acknowledged vendor lock-in, OPTIONAL (§5.11.4)
selection: strict           # runtime target selection, OPTIONAL (§5.10.6)
atomic: false               # forbid request splitting, OPTIONAL (§5.5)
x-typesafe:                 # vendor extension, OPTIONAL (§5.11)
```

The v0.1 keys `required_capabilities` and `fallbacks` do not exist in v0.2. Because the schema is closed (§5.1.2), a contract that uses either is `invalid_contract`, and the error message MUST name the migration command (§5.10.4).

See `examples/incident-triage.decision.yaml` and `examples/kyc-document-check.decision.yaml` for complete files.

### 5.1.1 Urim YAML profile

Contracts and lockfiles (`urim.lock`) are written in the **Urim YAML profile**, a strict subset of YAML 1.2 with the core schema. A conforming reader MUST accept every file that follows the profile and MUST reject any other file with a single error. It MUST apply these steps in this order and report only the first failure:

1. **Size.** The file MUST be at most 1 MiB (1,048,576 bytes) of UTF-8 and MUST be a regular file.
2. **Characters.** One leading byte order mark (U+FEFF) is ignored. Every other character MUST be YAML 1.2 `c-printable`, and MUST NOT be U+0085 (NEL), U+2028 (LS), U+2029 (PS) or U+FEFF.
3. **Well-formed YAML, in stream order.** The file MUST hold exactly one document, MUST be valid YAML 1.2, and MUST NOT use an undefined alias. Collections MUST NOT nest deeper than 64 levels. When nesting deeper than 64 and a syntax error both occur, the one that comes first in the stream is reported.
4. **Profile rules, first violation in the stream wins.** These are forbidden:
   - anchors and aliases (`&a`, `*a`);
   - tags of any kind (`!!str`, `!x`, `!<…>`);
   - the merge key `<<`, which is also never applied;
   - invisible or bidirectional-control characters in keys.

   On one node an anchor is reported before a tag.
5. **Values.** Mapping keys MUST be unique scalars. Every integer MUST be in −2^63..2^64−1. Plain scalars resolve with the YAML 1.2 core schema only, so `yes`, `no`, `on` and `off` stay strings.
6. **Schema.** The schema checks for the file kind then apply. Identifiers MUST NOT contain invisible characters.

Diagnostics that include a file name or file content MUST escape control, bidirectional and other invisible characters as `\u{XXXX}`, so a hostile name cannot rewrite the terminal or reorder what the reader sees.

The profile exists so that every reader in every language accepts the same files with the same meaning. Anchors, tags and merge keys are the features YAML parsers disagree on most. The reference checker (`urim check`, in JavaScript, Python and Rust) applies this profile, and its conformance cases live in the Urim repository (`CONTRACT.md` §3, `fixtures/cases.json`).

### 5.1.2 Typed, closed schemas and absent values

This section makes one guarantee: **a conforming tool never meets an undefined key, an untyped value, or an unstated default** in a contract or a lockfile.

**Rules.**

1. **Every key is typed.** Every key that may appear in a contract or a lockfile is listed in this section with exactly one type from the type vocabulary below. The published JSON Schemas encode the same types. No key has type "any".
2. **Schemas are closed.** A key that this section does not list at that position is an error: `invalid_contract` in a contract, `lock_violation` in a lockfile. The JSON Schemas MUST set `additionalProperties: false` (or `unevaluatedProperties: false`) on every object. The only exception is a vendor extension key `x-<provider>` at the positions §5.11.2 allows. Its own members are typed and closed by the registry's extension schema (§5.11.3), which MUST also be closed; a member that schema does not define is `invalid_contract`.
3. **No null, no empty value.** `null` is not a value of any type below. In YAML, a key with no value (`description:`) is `null` and is therefore an error. A key is either present with a value of its type, or absent.
4. **Absent has a written meaning.** Every OPTIONAL key below states what its absence means. That meaning is normative. A tool MUST apply exactly that meaning and MUST NOT substitute any other default, whether from its own configuration, an environment variable, a credential, or a provider response. Where an absent meaning is a value (for example `atomic` absent means `false`), the tool behaves as if that value were written; it MUST NOT write the value back into the file.
5. **REQUIRED means required.** A missing REQUIRED key is an error at the stage named in the table (load, compile, or plan). There is no fallback for a missing REQUIRED key.
6. **Lockfile keys are all REQUIRED.** A lockfile is machine-written by `apply`, so every lockfile key below is REQUIRED. A list or map that has no members is written empty (`[]`, `{}`), never omitted.
7. **Version gate.** A contract whose `urim` value is not a protocol version the tool supports MUST be rejected with `invalid_contract`, naming both versions. A tool MUST NOT read a contract of another protocol version with this version's schema.
8. **Expression strings.** Some keys are typed `expr`: a string whose inner grammar is still open (§13 item 3). The key and its string type are fixed now; a tool that cannot parse an `expr` MUST reject the file, never ignore the key.

**Type vocabulary.**

| Type | Values |
|---|---|
| `string` | Non-empty UTF-8 text, subject to §5.1.1. |
| `id` | A `string` matching `^[a-z][a-z0-9_-]{0,63}$`, not one of `__proto__`, `constructor`, `prototype` (PROPOSED, `security/THREAT-MODEL.md` §6.2; §13 item 3). |
| `target-id` | A `string` of the form `<provider>/<model>`, each segment an `id` (canonical format still §13 item 4). |
| `capability-path` | A `string` of dot-separated `id` segments naming a descriptor capability (§4.1), e.g. `limits.max_questions_per_request` (prefix scheme §13 item 6). |
| `semver` | A `string` that is a SemVer 2.0.0 version. |
| `semver-range` | A `string` that is a SemVer range (`^1.3.0`, `>=1.3.0 <2.0.0`). |
| `protocol-version` | A `string` of the form `"<MAJOR>.<MINOR>"` (quoted in YAML). This version: `"0.2"`. |
| `hash` | A `string` `sha256:<64 lowercase hex>`. |
| `integrity` | A `string` `sha256-<base64>` (§6.2). |
| `timestamp` | A `string` in RFC 3339 format with an explicit offset. |
| `integer` / `number` | A YAML/JSON number; `integer` has no fraction. Ranges are stated per key. Non-finite values (NaN, ±Infinity) are never valid. |
| `boolean` | `true` or `false` (YAML 1.2 core schema, so `yes`/`no` are strings, §5.1.1). |
| `enum(a \| b)` | Exactly one of the listed strings. |
| `list<T>` | A sequence whose items are all `T`. |
| `map<K, T>` | A mapping whose keys are `K` and whose values are `T`. `ordered map` preserves file order. |
| `expr` | A `string` whose inner grammar is open (rule 8). |

**Contract keys (top level).**

| Key | Type | Req. | Absent means |
|---|---|---|---|
| `urim` | `protocol-version` | REQUIRED (load) | — |
| `contract` | `id` | REQUIRED (load) | — |
| `version` | `semver` | REQUIRED (load) | — |
| `description` | `string` | OPTIONAL | The contract has no description. Nothing is sent to any provider either way. |
| `state` | `map<id, state-field>` (§5.2), at least one entry | REQUIRED (load) | — |
| `questions` | `ordered map<id, question>` (§5.3), at least one entry | REQUIRED (load) | — |
| `policy` | `map<id, policy-rule>` | OPTIONAL | No rule fires. Every answer's envelope `policy` member is `null` (§5.7), and `plan` fits no thresholds for this contract. |
| `confidence` | `confidence-block` | OPTIONAL | Portable confidence is computed with `top_probability` for `choice` and `score`, and with `yes_probability` for `yesno` (§5.4). |
| `eval` | `eval-block` (§7.1) | REQUIRED (plan); OPTIONAL (compile) | `compile` works; `plan` fails with `invalid_contract` naming the missing key. |
| `targets` | `list<target-id>`, no duplicates | OPTIONAL | Candidates come from `targets_query` alone. If both are absent, `compile` fails with `invalid_contract` (empty candidate set). |
| `targets_query` | `expr` | OPTIONAL | Candidates are exactly `targets`. |
| `requires` | `map<capability-path, constraint>` | OPTIONAL | No capability excludes any candidate. |
| `prefers` | `map<capability-path, preference>` | OPTIONAL | No soft preferences. Every capability the contract uses is then checked as a hard compile-time requirement against each candidate (§4.1, §5.9 rule 3); nothing is emulated or dropped. |
| `accept_lock_in` | `list<lock-in-ack>` | OPTIONAL | No lock-in is acknowledged, so any extension that locks out a candidate fails `compile` (§5.11.4). |
| `selection` | `enum(strict \| available)` | OPTIONAL | `strict` (§5.10.6). |
| `atomic` | `boolean` | OPTIONAL | `false`: splitting is allowed, but only where `prefers` declares the `split` emulation (§5.5 rule 3). |
| `x-<provider>` | `extension` (§5.11.3) | OPTIONAL | No extension for that provider. |

**Nested contract types.**

| Type | Keys (type, Req., absent means) |
|---|---|
| `state-field` | `type`: `enum(string \| markdown \| json \| image \| audio \| video)`, REQUIRED. `required`: `boolean`, OPTIONAL, absent = `false` (the field may be omitted from a call). `max_bytes`: `integer` ≥ 1, OPTIONAL, absent = only the target's `limits.max_state_bytes` and the runtime's own resource limits (§D.1.2 `limit_exceeded`) apply. `schema`: a JSON Schema 2020-12 object, allowed only when `type` is `json`, OPTIONAL, absent = any JSON value is accepted for that field. |
| `question` | `type`: `enum(choice \| score \| yesno \| box \| extract)`, REQUIRED. `instructions`: `string`, REQUIRED. `options`: `map<id, string>`, REQUIRED for `choice` and invalid otherwise. `levels`: `list<string>` with at least 2 items, REQUIRED for `score` and invalid otherwise. `"yes"`, `"no"`: `string`, allowed only for `yesno`, OPTIONAL, absent = no description is sent for that side. `box` and `extract` take no answer-space keys in v0.2 (their answer spaces are provider-specific and go through `x-<provider>`, §5.11). `x-<provider>`: `extension`, OPTIONAL. |
| `policy-rule` | `question`: `id` of a declared question, REQUIRED. `when`: an object with exactly one key `answer`, whose value is a `string` naming an option key (`choice`), `"yes"`/`"no"` (`yesno`) or a zero-based level index as a string (`score`), OPTIONAL, absent = the rule is evaluated on the question's top answer, whatever it is. `applies_to`: `enum(native \| portable)`, REQUIRED; `portable` means the definition that `confidence` (or its absent meaning) assigns to the question's type (§5.4; whether a rule may name a definition directly is §13 item 8). `objective`: an object with exactly one of `min_precision` (`number` in (0, 1]) or `escalation_rate` (`number` in [0, 1]), REQUIRED. `action`: `id`, REQUIRED. `else`: `id`, OPTIONAL, absent = when the rule does not fire, no action is reported (`policy.action` absent, `fired: false`). `on_error`: `id` (PROPOSED key name), OPTIONAL, absent = the generic `escalate` signal (§D.2.2); never `else`. Absent-question behavior for a rule whose question may be dropped: key TODO (D-16, §5.10.3 rule 3); until it is named, such a rule makes `compile` fail. |
| `confidence-block` | `portable`: `string` naming a registered definition for `choice` and `score` (§5.4), REQUIRED within the block. `yesno` questions always use `yes_probability`. |
| `eval-block` | `dataset`: `string` (relative path), REQUIRED. `dataset_hash`: `hash`, REQUIRED. `min_cases`: `integer` ≥ 1, REQUIRED. `repeats`: `integer` ≥ 1, OPTIONAL, absent = `1`; with one repeat, run-to-run noise (§7.2) is reported as "not measured". `paraphrases`: `map<id, list<string>>` keyed by question id, OPTIONAL, absent = wording sensitivity is reported as "not measured". `accept`: `map<id, expr>` keyed by metric name, REQUIRED. |
| `constraint` | One of: a lifecycle `enum(ga \| experimental)`; a comparison `expr` such as `">= 3"`; `{ includes: list<string> }`; or `{ any_of: list<string> }`. Constraint grammar: §13 item 3. |
| `preference` | `{ fallback: fallback }` or `{ value: constraint, fallback: fallback }`. `fallback` is REQUIRED; there is no implicit fallback (§5.10.3). |
| `fallback` | `drop`, `fail`, or `{ emulate: id }` naming a registered emulation (§5.10.3). |
| `extension` | `fallback`: `fallback`, OPTIONAL, absent = `fail` for every target of another provider (§5.11.4). `with`: an object typed and closed by the registry's extension schema, REQUIRED (PROPOSED key name). |
| `lock-in-ack` | `extension`: the `x-<provider>` key, REQUIRED. `locks_out`: `list<target-id>`, REQUIRED, equal to the resolver's computed set. `reason`: `string`, REQUIRED. |

**Lockfile keys.** §6.2 lists them, each with its type. Every one is REQUIRED (rule 6).

**What the descriptor and the envelope inherit.** Descriptors (§4.1) and envelopes (§5.7) follow rules 1, 3 and 4: typed keys, no `null` except where a field is specified as nullable (for example `confidence.native`, §5.7), and stated absent meanings. Their closure rules belong to their own schemas (§10 M0).

### 5.2 State

`state` declares named inputs with a type: `string`, `markdown`, `json` (with optional inline JSON Schema), `image`, `audio`, `video`. Fields MAY be marked `required` and MAY carry `max_bytes`; the types and absent meanings are in §5.1.2 (`state-field`). The compiler serializes state into each target's native `state` representation. Modalities not supported by a target are a compile-time error, unless the target was excluded by `requires` (§5.10.2).

### 5.3 Questions

Questions are an **ordered** map from a stable question id to a definition. Every question MUST have `type` and `instructions`.

| Urim type | Answer space | `systemone` native | `decisions` native |
|---|---|---|---|
| `choice` | `options`: map of key → description, ≥ 1 (≥ 2 RECOMMENDED) | `choice` | `choice` |
| `score` | `levels`: ordered list of descriptions, ≥ 2 | `score` | `score` |
| `yesno` | `yes` / `no` descriptions (either MAY be omitted) | `noul` | `predicate` |
| `box` *(experimental)* | image region | provider-specific (e.g. Jev `box`, experimental, opt-in header) | provider-specific |
| `extract` *(experimental)* | span or value from state | provider-specific (e.g. Inception Mercury Decide `extract`: 1–26 named fields, returns spans) | provider-specific |

Rules:

- Question ids MUST be stable across contract versions; renaming one is a breaking change (§6.1).
- Option keys MUST be stable identifiers, distinct from display descriptions, so code and policy can refer to them.
- An experimental question type MUST be declared in `requires` or `prefers` (§5.10). In `prefers`, its fallback MUST be `drop` or `fail`; no emulation of an experimental type is registered. Declaring a `drop` is a contract MAJOR (§6.1, D-13), and dropping a question that a policy rule references is a compile error unless the rule declares absent-question behavior (§5.10.3 rule 3, D-16). A contract that uses an experimental type without declaring it is `invalid_contract`.
- In YAML, the `yes`/`no` keys and values MUST be quoted (`"yes"`), because YAML 1.1 parsers read bare `yes`/`no` as booleans. Contract parsers MUST use YAML 1.2 core schema or reject boolean keys (§5.1.1).
- `instructions` is a `string` in v0.2 (§5.1.2). A structured form is reserved for a later version; a contract that uses an object for `instructions` is `invalid_contract`. Compilers MUST serialize the string into the form each target accepts.
- A `choice` with fewer options than the target's `min_choice_options` MUST be rejected at compile time. OpenAI Decisions and Workers AI Clef require at least 2, so a one-option choice cannot compile for them. The contract-level minimum stays ≥ 1.

### 5.4 Confidence

Urim never redefines a provider's `confidence`. It adds an optional, declared **portable confidence** computed client-side from the returned distribution. These definitions are registered (unchanged since v0.1):

| Name | Definition over distribution *p* (sorted descending) |
|---|---|
| `top_probability` | p₁ |
| `margin` | p₁ − p₂ |
| `margin_squared` | (p₁ − p₂)². **UNSOURCED** as Clef's definition: no primary source found on 2026-10-25. Cloudflare docs say only that confidence shows "how concentrated the probabilities are", and one published Clef-flash response fits normalized Gini better than margin². Kept as a formula; not attributed. |
| `one_minus_entropy` | 1 − H(p) / log(n) |
| `yes_probability` | P(yes), for `yesno` only |
| `normalized_top` | (p₁ − 1/n) / (1 − 1/n). Documented as native choice confidence by TypeSafe Jev (docs.typesafe.ai/confidence) and Perplexity Decider. |
| `abs_2p_minus_1` | \|2·P(yes) − 1\|, for `yesno` only. Documented as native noul confidence by Fastino GLiDE (huggingface.co/fastino/GLiDE). |

Native definitions observed on 2026-10-25 (non-normative): Fastino GLiDE uses `margin` for choice and score; Jev and Perplexity use `normalized_top` for choice. Jev's score confidence is max(0, 1 − Σ pᵢ·\|i − m\| / MAD_unif), and Perplexity's is 1 − spread / baseline. Both are documented but not yet registered. **OPEN-DECISION (David): naming of the score-spread definitions.** Jev, Clef, Perplexity and OpenAI return no native confidence for yes/no (`noul`/`predicate`); GLiDE does.

Policy thresholds MUST reference either `native` or a named portable definition, never an unlabeled "confidence". Portable confidence makes thresholds **comparable in form**, not **calibrated across models**; fitted values still differ per model and live in the lockfile (§6.2). This mirrors the AI SDK's position, which preserves native values and makes no cross-provider calibration promise.

### 5.5 Request transpilation

For each (contract, target), the compiler produces the native request. A conforming compiler MUST:

1. Map each Urim question type to the target's native type using its descriptor (`yesno` → `noul` or `predicate`).
2. Map option keys and score levels into the target's native criteria structure, preserving key identity and level order.
3. **Split** the question set into multiple requests only where the target's resolution records `limits.max_questions_per_request` as `emulated` via `split` (the contract declared `prefers: { limits.max_questions_per_request: { …, fallback: { emulate: split } } }`, §5.10.3), and merge the answers, preserving question order. Without that declaration, a question set that exceeds the target's `max_questions_per_request` is `capability_unsupported` for that target. A contract that sets `atomic: true` and also declares the `split` emulation is `invalid_contract`.
4. Reject (at compile time) any `choice` with fewer than `min_choice_options` or more than `max_choice_options` options, or any `score` outside `score_levels`.
5. Never include policy or thresholds in the request.
6. Emit a deterministic request: the same contract, state, and target MUST produce byte-identical request bodies (excluding auth and request ids), so requests can be hashed into the lockfile and replayed.
7. Record the compiled request hash in the response envelope.

Splitting changes encoder context on some servers (jevcompat reportedly observed one server whose answer moved from 0.768 to 0.351 when question order was reversed; this figure is UNVERIFIED and was not located in jevcompat's public docs on 2026-10-25). `plan` therefore measures order sensitivity (§7), and a lockfile entry MUST record the split strategy it was evaluated with (`split_strategy`, §6.2).

### 5.6 Adapters as compile targets

A target with `camp: adapter` compiles to a call into an existing library rather than raw HTTP. v0.2 names these adapter targets (exact call shapes are defined by each adapter's documentation and owned by its target plugin):

- Vercel AI SDK `experimental_decide` and AI Gateway `/v1/evaluate` (yes/no type named `boolean`)
- LiteLLM decisions
- OpenRouter
- Pydantic AI `DecisionModel`

When compiling to an adapter, the adapter's own response normalization MUST be preserved in `raw`, and Urim's envelope is built on top of it. Adapter-level failover (e.g. AI Gateway's single low-confidence retry on a backup model) MUST be disabled, because it can change the answering model without a `plan`. Where an adapter offers no way to disable it, the target's descriptor MUST say so, and the runtime MUST record the answering model reported by the adapter and check it against the lock (§D.2.1 rule 7; a mismatch is `lock_violation`, §D.1.2). Urim's own failover is defined in §D.2.

### 5.7 Normalized response envelope

Every call returns one envelope regardless of target:

```json
{
  "urim": "0.2",
  "contract": "incident-triage@1.3.0",
  "target": { "id": "cloudflare/clef-flash", "provider": "cloudflare", "model": "clef-flash",
              "model_version": "2026-10-01", "camp": "systemone", "role": "active" },
  "request_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "answers": {
    "page": {
      "type": "yesno",
      "answer": "yes",
      "distribution": { "yes": 0.83, "no": 0.17 },
      "confidence": { "native": null, "native_definition": null,
                      "portable": 0.83, "portable_definition": "yes_probability" },
      "policy": { "threshold": 0.78, "source": "lock", "action": "page_oncall", "fired": true }
    }
  },
  "failover": null,
  "usage": { "latency_ms": 41, "cost": { "amount": 0.00012, "currency": "USD", "basis": "per_token", "estimated": true } },
  "raw": { "…": "native response, verbatim" }
}
```

Envelope rules:

- *Example notes:* values match `examples/urim.lock`. `native` is null because Clef returns no confidence for `noul` answers. `model_version` "2026-10-01" is a PLACEHOLDER (see §4.1 on pinning). Cost is `estimated` because the example descriptor's pricing is not yet filled. **OPEN-DECISION (David): canonical target-id format** (`provider`+`model` vs a single `vendor/model` id as used in contracts and lockfiles; §13 item 4). Until it is decided, `target` carries both forms; all six members (`id`, `provider`, `model`, `model_version`, `camp`, `role`) are REQUIRED, and `role` is `active` or `standby`.
- Nullable members are exactly these: `confidence.native`, `confidence.native_definition`, `confidence.portable` and `confidence.portable_definition` (null when no portable definition applies), `policy` (null when no rule references the question, §5.1.2), and `failover` (null when no failover or `selection: available` skip happened). Every other member is typed and non-null.
- `confidence.native` MUST be `null` when the provider returns no native confidence, for example for `noul` on Jev, Clef or Perplexity, or OpenAI `predicate`.
- `distribution` MUST use contract option keys (choice), `yes`/`no` (yesno), or zero-based level indices as strings (score), and MUST sum to 1 within 0.0001 after the compiler's mapping. For `score`, the envelope MUST also include `expected_level` (probability-weighted index), consistent with DMP. It is computed from `distribution` and never copied from the native `score` field, because native score semantics differ: Jev, Clef and Inception return the probability-weighted level, while Fastino GLiDE returns the argmax level and reports the expectation separately as `expected_level`.
- `raw` MUST contain the unmodified native response. Configuration MAY make it absent in production (absent, never `null`); it MUST be present during `plan`.
- `policy` is computed by the Urim Runtime (or another runtime, §2) from the lockfile, not by the provider.
- `failover`, when not null, records the move with exactly the members `from`, `reason`, `attempts` and `exhausted` (§D.3.5); the rules are in §D.2.

**Error envelope.** Failures return the error object of §D.1, whose classifier member is `type` (the v0.1 member `kind` is removed in 0.2; see CHANGELOG.md). §D.1.2 lists every `type`, its retry and failover eligibility, and its breaker behavior. Three types separate the ways a response can be wrong (§D.1.3): a response that fails the schema or types is `response_schema_violation`; a response from a target, model version or resolution other than the locked one is `lock_violation`; a well-typed response that breaks a semantic rule (e.g. a distribution that does not sum to 1, or a chosen key that is not the argmax) is `nonconformant_response`. None of them is silently repaired. Partial success (some questions answered) MUST be reported per question.

### 5.8 Typed codegen (later milestone)

From a contract, generators SHOULD emit typed clients for TypeScript, Python, and Go: a state input type, a result type with option keys as literal unions/enums, and a `decide()` function returning the envelope. Codegen is out of scope for MVP (§10, M5) and SHOULD reuse Buf's `protoc-gen-jev` and Pydantic AI type models where practical.

### 5.9 Capability-gated resolver

A contract feature is available to code **only** when every target it may run on supports it. The resolver enforces this at **compile time** and again at **plan time** (against the descriptor version being locked), never first at call time.

Prior art: Terraform's provider schemas and `required_providers` block (declare the providers and version ranges you depend on; the tool refuses configurations the provider schema does not accept), and browserslist + Babel `preset-env` + caniuse (declare targets once; the compiler enables, transforms, or polyfills each feature according to a capability table).

**Declaring targets and requirements.** A contract declares candidate targets with `targets` and `targets_query`, and declares the capabilities it needs with `requires` (hard) and `prefers` (soft, with a declared fallback). Their semantics are §5.10. The v0.1 keys `required_capabilities` and `fallbacks` are replaced (§5.10.4).

**Gated features (v0.2 set):** non-text modalities (`image`, `audio`, `video`); experimental question types (`box`, `extract`); typed refusal; question count above a target's limit; choice size and score levels above limits; prompt/state caching; data residency and private networking; open-weight license constraints; vendor extensions (§5.11).

**Resolution rules.**

1. The resolver evaluates `targets_query` against the registry to produce the candidate target set, then intersects it with any explicit `targets`. (If only one of the two is present, the candidate set is that one; if neither is, see §5.1.2.)
2. For each feature the contract uses and each candidate target, the resolver looks up the descriptor. The outcome is one of: `native` (supported), `emulated` (a declared `emulate` fallback applies, e.g. `split` for question limits, or `map_error` for refusal), `dropped` (a declared `drop` fallback applies), or `unsupported`. ("Polyfill" remains the prose name for the emulation mechanism; the recorded outcome value is `emulated`.)
3. `unsupported` MUST fail with an error naming the feature, the target, the descriptor version and its source URL, and the declarations that would make it compile. Example: `capability_unsupported: question_types.box is not supported by clef-flash (descriptor 1.4.0, source …); declare prefers.question_types.box with fallback drop, or remove the target.` §5.10.2 and §5.10.3 say when an unsatisfied feature excludes a target instead.
4. An emulation MUST be a documented, deterministic transform with known effects. Emulations and drops that change decision behavior (such as `split`, which changes shared context) MUST be evaluated by `plan` with exactly that resolution active, and the lockfile records it (`resolution`, §6.2).
5. Generated typed clients (§5.8) MUST expose an optional or dropped feature as optional in the type (e.g. `box?: Box`), so code cannot assume it exists on every target.
6. The resolver MUST emit a capability report (feature × target matrix with the outcome) as part of `compile` and `plan` output, like a caniuse table for the contract, extended with the portability section of §5.10.5.

The resolver runs at compile and plan time only. A runtime MUST NOT re-run capability resolution; it executes the resolution recorded in the lockfile (§6.2, §5.10.6). (This restates `security/THREAT-MODEL.md` R3, "the registry is consumed at plan time only", as normative text.)

### 5.10 Capability requirements and preferences

#### 5.10.1 Keys

A contract MAY declare `requires` and `prefers` at the top level. Both map a **capability path** (§4.1 descriptor vocabulary; the `features.` prefix question is §13 item 6) to a constraint.

```yaml
# incident-triage.decision.yaml (excerpt; matches examples/incident-triage.decision.yaml)
urim: "0.2"
contract: incident-triage
version: 1.3.0                    # migrated to protocol 0.2; MINOR per §6.1

requires:                         # hard: targets that don't satisfy are excluded
  question_types.choice: ga
  question_types.score: ga
  question_types.yesno: ga

prefers:                          # soft: each entry MUST declare a fallback
  limits.max_questions_per_request:
    value: ">= 3"
    fallback: { emulate: split }  # below 3: split into several requests (emulated)
  refusal.typed:
    fallback: { emulate: map_error }

targets_query: "camp:any, not experimental"
targets:
  - typesafe/jev
  - cloudflare/clef-flash
  - openai/decisions
```

Other entry shapes appear in the §5.10.3 table: `fallback: drop` (e.g. `caching.prompt`) and `fallback: fail` (e.g. `question_types.box`, D-15). The kyc example uses `question_types.box: { fallback: drop }`.

**Constraint syntax.** A bare value (`ga`, `experimental`, `">= 3"`, `{ includes: [...] }`) means what it meant in v0.1 `required_capabilities`. Types: §5.1.2 (`constraint`, `preference`). In `prefers`, the long form `{ value, fallback }` is used when a value is needed. When it isn't, use `{ fallback }` alone. The constraint grammar is still §13 item 3.

#### 5.10.2 `requires` (hard)

1. The resolver MUST first compute the candidate set (§5.9 rule 1: `targets_query` intersected with explicit `targets`). It MUST then **exclude** every candidate whose locked descriptor does not satisfy every `requires` entry.
2. Every exclusion MUST appear in the capability report. The report names the target, the failing capability path, the descriptor value, the descriptor version, and its source URL.
3. If an **explicitly listed** `targets` entry is excluded, `compile` MUST fail with `capability_unsupported` and the §5.9 rule 3 message. Pruning is silent-but-reported only for targets that came in through `targets_query`. Rationale: if the author named a target, dropping it quietly would surprise them.
4. If the candidate set is empty after exclusion, `compile` MUST fail and list each excluded target with its reasons.
5. `requires` MUST NOT declare a fallback. A `requires` entry that carries `fallback` is `invalid_contract`.

#### 5.10.3 `prefers` (soft, with declared fallback)

Every `prefers` entry MUST declare exactly one fallback. A `prefers` entry without one is `invalid_contract`; there is no implicit default. This removes v0.1's implicit "error (default)" for `fallbacks`.

| Fallback | Meaning on a target whose descriptor lacks the feature | Resolution outcome (§5.9 rule 2) | Typed client (§5.8) |
|---|---|---|---|
| `emulate: <name>` | Apply the named, registered emulation (a polyfill, in §5.9's terms). `<name>` MUST be one the spec or registry defines for that capability path (v0.2: `split` for `limits.max_questions_per_request`, `map_error` for `refusal.typed`). An unknown name is `invalid_contract`. | `emulated` (renamed from v0.1 `polyfill`, D-12) | unchanged |
| `drop` | Don't use the feature on that target. For a question-type feature, drop the affected questions (v0.1 `drop_question`). For a non-question feature (e.g. `caching.prompt`), ignore it (v0.1 `ignore`). | `dropped` | affected answers become optional (§5.9 rule 5); introducing such a drop is a contract **MAJOR** (§6.1, D-13) |
| `fail` | Keep the target in the candidate set and fail resolution for it with `capability_unsupported`. Unlike `requires`, this never prunes silently, even for query-derived targets (D-15). An operator can apply `fail` to every `prefers` entry for one run with `--strict-prefers` (§7.4). | `unsupported` | — |

Rules:

1. Where the descriptor says the feature is supported, the outcome is `native`, whatever fallback was declared.
2. `emulate` and `drop` change behavior. `plan` MUST evaluate each target with exactly its resolved combination of `native` / `emulated` / `dropped` outcomes (§5.10.5). This extends §5.9 rule 4 from polyfills to drops.
3. **(D-16)** `drop` on a question that a `policy` rule references MUST be a compile error, unless that rule also declares what happens when its question is absent. Rationale: a dropped question must not silently disable a gate such as `page_oncall`. The key for this is TODO and depends on the §13 item 3 policy grammar. Whatever the key is, it MUST NOT default to the rule's `else` (§D.2.2, D-22).
4. If a feature appears in both `requires` and `prefers`, the contract is `invalid_contract`.

#### 5.10.4 Migration from `required_capabilities` / `fallbacks`

| v0.1 form | v0.2 form |
|---|---|
| `X: required` / `X: ">= ga"` | `requires: { X: ga }`. `required` and `">= ga"` are not v0.2 `constraint` values (§5.1.2), so the migration rewrites both to `ga` and reports each rewrite for the author to confirm. |
| `X: "<range>"` (e.g. `">= 3"`) with no fallback | `requires: { X: "<range>" }` (same value) |
| `X: optional` + `fallbacks.X: drop_question` or `ignore` | `prefers: { X: { fallback: drop } }` |
| `X: optional` + `fallbacks.X: split` or `map_error` | `prefers: { X: { fallback: { emulate: split } } }` (or `map_error`) |
| `X: optional` + `fallbacks.X: error` (or no fallback) | `prefers: { X: { fallback: fail } }` |
| `X: ">= 3"` + `fallbacks.X: split` (incident-triage example) | `prefers: { X: { value: ">= 3", fallback: { emulate: split } } }`. The v0.1 pairing was ambiguous; v0.2 reads it as soft. |

**(D-10) Replace, no aliases.** In a `urim: "0.2"` contract, `required_capabilities` and `fallbacks` are not aliases: either key MUST be `invalid_contract` (§5.1.2 rule 2), and the error message MUST name the migration command. A v0.1 file is read only by a tool that supports protocol 0.1, with its v0.1 keys and v0.1 meaning (§5.1.2 rule 7). The v0.1 spelling of the version key is recorded in CHANGELOG.md.

The reference tooling MUST ship a mechanical migration (command name TODO, e.g. `urim migrate`). It rewrites per the table above, rewrites the version key to `urim: "0.2"`, writes an explicit `fallback` for every `prefers` entry (v0.1's implicit "error (default)" becomes `fail`), and reports every ambiguous pairing such as the `">= 3"` + `split` row for the author to confirm. Because the rewrite changes the contract's bytes and can change resolution, the migrated contract needs a new `plan` (§6.2).

This settles the v0.1.1 box-fallback conflict (old §13 item 2): `prefers` requires an explicit fallback, so there is no implicit default left to conflict (§5.3).

#### 5.10.5 Plan: per-target portability report

`plan` (and `compile`, without metrics) MUST extend the §5.9 rule 6 capability report with a **portability section**:

1. For each candidate target: included or excluded (and why), resolution `mode` (§6.2), and the outcome for every capability path the contract uses.
2. For each vendor extension (§5.11): the targets it applies to, its fallback for every other target, and the **targets it locks out**.
3. A one-line summary per contract: *N of M candidates lockable; extensions locking out K targets: `x-…` → [targets]*.

Example (`urim plan` text output; the format is illustrative and not normative):

```text
incident-triage@1.3.0  portability: <n> of 3 candidates lockable
                          typesafe/jev   cloudflare/clef-flash   openai/decisions
question_types.choice     native         native                  native
question_types.score      native         native                  native
question_types.yesno      native         native                  native (predicate)
limits.max_questions…     native         native                  TODO(vendor-fact)
refusal.typed             emulated       emulated                TODO(vendor-fact)
caching.prompt            TODO           TODO                    TODO
x-typesafe (fallback:drop) applied      dropped                 dropped
mode                      emulated       degraded                TODO (included or excluded per its descriptor)
```

(The cells reflect `examples/urim.lock`, where they exist, or are TODO. This specification asserts no new vendor facts.)

#### 5.10.6 Runtime target selection: credentials never unlock features

1. A runtime MUST execute only (target, resolution) pairs recorded in the lockfile. The resolution in the lockfile is the behavior. A runtime MUST NOT add, upgrade, or re-resolve a feature because of anything it observes at runtime: an API key, an account tier, an environment variable, a header returned by the provider, or a newer descriptor.
2. Credentials and environment configuration MAY only **select among** lockfile targets. Default `selection: strict` uses `active` and moves to `standby` only under the failover rules of §D.2. An opt-in `selection: available` (PROPOSED) MAY skip, in lockfile order, targets for which no credential is configured. Every such skip MUST be recorded in telemetry and in envelope metadata, just like failover.
3. An environment override that pins a target (variable name TODO, e.g. `URIM_TARGET`) MUST name a target in the lockfile. Otherwise the runtime MUST refuse with `lock_violation` (§D.1.2).
4. If a provider rejects a request because the account lacks a locked feature (for example, the feature is gated to a tier), the result is `capability_unsupported` at runtime. It is never a silent downgrade to `drop`.

**Rationale.** The same contract and lockfile must not behave differently on a laptop with an enterprise key and on CI with a free-tier key. Thummim fitted the thresholds for one combination. If any other combination runs, the thresholds no longer mean what `plan` measured (principle 4), and principle 5 (switching is gated by evidence) can be bypassed by setting an environment variable (TM R2/N4). Under `selection: available`, different machines can still be answered by *different locked targets*. Each one was evaluated, though, and the switch is visible. That is why `strict` is the proposed default.

### 5.11 Vendor extensions

#### 5.11.1 Naming

A vendor extension is a contract key of the form `x-<provider>`, where `<provider>` is the provider segment of a canonical target id (today's examples use `vendor/model`, so `x-typesafe` and `x-cloudflare`; this depends on §13 item 4). The pattern follows OpenAPI Specification Extensions. OAS 3.2.1 says: "The field name MUST begin with `x-`… Field names beginning `x-oai-` and `x-oas-` are reserved for uses defined by the OpenAPI Initiative" (https://spec.openapis.org/oas/latest.html, read 2026-10-26).

- Names beginning `x-urim-` are RESERVED for this specification and its reference tooling.
- `<provider>` MUST match the registry's provider id grammar (TM §6.2 identifier grammar proposal).

#### 5.11.2 Where extensions may appear

- At the contract top level (request-wide), and inside a single question (question-scoped).
- They MUST NOT appear inside `state`, `policy`, `confidence`, `eval`, `requires`, `prefers`, or `targets`. Policy and thresholds stay outside the model (§2 "Policy"). An extension cannot move them into a request.

#### 5.11.3 Shape and validation

```yaml
x-typesafe:                         # request-wide extension
  fallback: drop                    # for targets of every other provider: drop | fail | { emulate: <name> }
  with:                             # PROPOSED key; contents are defined by the provider's extension schema
    TODO(vendor-fact): "no TypeSafe extension keys are asserted by this draft"

questions:
  severity:
    type: score
    # ...
    x-cloudflare:                   # question-scoped extension
      fallback: drop
      with: { TODO(vendor-fact): "…" }
```

1. **Schema from the registry (D-17).** The provider's registry descriptor MUST publish a JSON Schema for every extension key it accepts, together with an effect class, in the descriptor field group `extensions` (§4.1; its own schema is TODO). The schema is registry data: it goes through the drift pipeline (§4.3), carries provenance, and is hash-pinned in the lockfile (`schema_hash`). A target plugin MUST NOT define or widen extension schemas in code; it only maps already-validated `with` contents into the native request. The effect class is either `transport` (it can't change answers, e.g. a priority hint) or `behavioral` (it can).
2. **Strict.** The schema MUST be closed. An `x-<provider>.with` member that the schema does not define MUST be `invalid_contract` (§5.1.2 rule 2). Typos must not pass silently.
3. **Not for secrets or routing.** An extension MUST NOT carry credentials, endpoints, hosts, or auth headers, and MUST NOT override the descriptor's endpoint or auth (TM C6, R1; TM §6.1 proposed 14.6 and 14.7). The compiler MUST serialize `with` contents as data (TM C1, 14.3), never as templated text.
4. **Applies to its provider only.** When compiling for a target of `<provider>`, the target plugin maps `with` into the native request. For every other provider, `fallback` decides what happens: `drop` ignores it, `{ emulate: <name> }` uses a registered emulation, and `fail` makes that target unsupported.
5. **Evaluated.** A `behavioral` extension changes decisions. `plan` MUST evaluate the target with the extension applied, and the lockfile records it (§6.2).
6. If no candidate target belongs to `<provider>`, the extension is dead code. The compiler SHOULD warn.

#### 5.11.4 Acknowledging lock-in

An extension **locks out** a target when it is `fallback: fail` for that target, or when it has no fallback at all. A contract in which any extension locks out any candidate target MUST carry an explicit acknowledgement. Without one, `compile` MUST fail and name the extension and the targets it locks out:

```yaml
accept_lock_in:                    # PROPOSED key name
  - extension: x-typesafe
    locks_out: [cloudflare/clef-flash, openai/decisions]   # MUST equal the resolver's computed set
    reason: "Needs <feature>; revisit when it is portable (see §6.3)."
```

- `locks_out` MUST match the computed set exactly. If the registry later adds providers, the set changes, `plan` fails, and someone has to re-acknowledge. Lock-in cannot grow without a reviewed diff.
- An extension with `fallback: drop` or `emulate` locks nothing out. It needs no acknowledgement, but it still appears in the portability report, because `drop` changes behavior on the other targets.
- Absent `fallback` is treated as `fail`, so it always needs an acknowledgement. This is "fail closed" for portability.

---

## 6. Part C — Version control

### 6.1 Contract semver

| Change | Bump |
|---|---|
| Rename or remove a question, option key, or state field; change a question's type; reorder or remove score levels; change `atomic` | **MAJOR** |
| Introduce a `drop` that can remove a question from any target's response: add a `prefers` entry on a question-type feature with `fallback: drop`, or change such an entry's fallback to `drop` | **MAJOR** (D-13): the generated typed client's field becomes optional (§5.9 rule 5), which breaks callers |
| Add a question; add an option to a `choice`; add an optional state field; change `instructions` or option descriptions; change portable confidence definition | **MINOR** |
| Add a `requires` / `prefers` entry or an `x-` extension (the contract adopts a feature) not covered by the drop row; change an entry's fallback (other than to `drop` as above); move an entry between `requires` and `prefers`; change `with` contents of a `behavioral` extension; change `accept_lock_in`; change `selection` | **MINOR** |
| Remove a `requires` entry (this widens the target set) or a `prefers` entry | **MINOR** |
| Change `with` contents of a `transport`-class extension | **PATCH** (D-13). The effect class comes from the registry (D-17), so the compiler, not the author, decides whether an edit qualifies. If the registry reclassifies the key as `behavioral`, the same edit becomes MINOR. |
| Edit metadata, description, eval set additions that do not change acceptance criteria | **PATCH** |

Any MINOR or MAJOR change MUST invalidate every lockfile entry's fitted thresholds for that contract and require a new `plan`. Wording changes are MINOR, not PATCH, because decision models are measurably sensitive to wording. An adopted feature changes the request, so it changes behavior; apart from the transport-extension row, a contract cannot make any capability change as a PATCH.

Scope note on D-13: "`drop` = MAJOR" applies where `drop` can remove an answer (question-type features). `drop` on a non-question feature such as `caching.prompt`, or an `x-` extension's `fallback: drop`, changes no type and stays MINOR. That reading awaits David's confirmation (§13 item 9).

### 6.2 Lockfile (hoshen format)

The hoshen is the lockfile format: it holds what was decided and measured, so a verdict can be reproduced. The lockfile is named `urim.lock`. It is generated by `plan`/`apply` and SHOULD be committed. It is the **only** source of live targets and thresholds. This section defines **`hoshen: 2`** (D-14). No `hoshen: 1` lockfile has been published, so no reader or writer needs to support `hoshen: 1`.

Every key below is REQUIRED (§5.1.2 rule 6), and the lockfile schema is closed (§5.1.2 rule 2): an unknown or missing key is `lock_violation`.

**Top level.**

| Key | Type | Meaning |
|---|---|---|
| `hoshen` | `integer` | Format version of the lockfile itself. This version: `2`. |
| `urim` | `protocol-version` | Protocol version the lockfile was generated against. This version: `"0.2"`. |
| `generated_at` | `timestamp` | Time of the `apply` that wrote the file. |
| `compiler` | `{ name: id, version: semver }` | Tool that wrote the file (e.g. `{ name: urim, version: 0.2.0 }`). |
| `integrity` | `integrity` | See the integrity rule below. |
| `contracts` | `map<id, contract-entry>` | One entry per contract id. |

**`contract-entry`.**

| Key | Type | Meaning |
|---|---|---|
| `version` | `semver` | Contract version that was planned. |
| `content_hash` | `hash` | Hash of the contract's canonical form (§13 item 5). |
| `eval` | `{ dataset_hash: hash, cases: integer ≥ 1 }` | Eval set that justified the entry. |
| `active` | `target-id` | Target served by default. MUST be a key of `targets`. |
| `standby` | `list<target-id>` | Ordered failover candidates (§D.2); each MUST be a key of `targets`; MAY be `[]`. |
| `selection` | `enum(strict \| available)` | Copied from the contract, or `strict` when the contract omits it (§5.10.6). |
| `accept_lock_in` | `list<lock-in-ack>` | Copied from the contract; `[]` when the contract omits it. |
| `targets` | `map<target-id, target-entry>` | Every target that may serve, with its fitted thresholds. |

**`target-entry`.**

| Key | Type | Meaning |
|---|---|---|
| `camp` | `enum(systemone \| decisions \| adapter)` | Camp of the target (§2). |
| `model` | `string` | Provider model id. |
| `model_version` | `string` | Pinned model version (D-31: the same name as `fitted_for.model_version`, the envelope `target` and the error object `target`). Aliases such as `jev-latest` MUST be resolved to a concrete version. |
| `descriptor` | `{ version: semver, range: semver-range, hash: hash }` | Descriptor version resolved at lock time, the acceptable range (written explicitly; `apply` writes `^` of the locked version unless told otherwise), and its hash. |
| `split_strategy` | `enum(none \| split)` | Whether `plan` evaluated this target with the `split` emulation active (§5.5 rule 3). |
| `resolution` | `resolution` (below) | The capability resolution that `plan` evaluated (§5.10). |
| `thresholds` | `map<id, threshold>` keyed by policy rule id | One entry for every policy rule; `{}` when the contract has no `policy`. |
| `metrics` | `map<id, number \| boolean>` | §7.2 metrics at the fitted thresholds, plus `measured: boolean` (§7.3). |
| `plan_report` | `hash` | Hash of the `plan` report that justified the entry. |

**`resolution`.** `source`: `enum(explicit | query)`. `mode`: `enum(exact | emulated | degraded)` (`exact` = all native; `emulated` = at least one emulated, no drops; `degraded` = at least one drop). `features`: `map<capability-path, outcome>`, where an outcome is either the string `native` or `{ outcome: enum(emulated | dropped), via: id (emulated only), declared: enum(requires | prefers) }`. `extensions`: `map<x-key, { outcome: enum(applied | dropped | emulated), effect: enum(transport | behavioral), schema_hash: hash (applied only) }>`, `{}` when the contract has none. `hash`: `hash` over the RFC 8785 JCS of `{features, extensions, split_strategy, descriptor.hash}` (exact input set: §13 item 5). Types are those of §5.1.2.

**`threshold`.** `confidence`: `string`, `native` or `portable/<definition>`. `value`: `number` in [0, 1]. `method`: `string` naming the fitting objective (e.g. `min_precision_0.95`). `fitted_for`: `{ contract_version: semver, model_version: string, resolution: hash }`.

```yaml
# urim.lock (hoshen 2) — fragment; full file: examples/urim.lock. Every hash is an all-zero
# placeholder of the right type (§5.1.2), so this fragment deliberately FAILS the integrity check.
hoshen: 2
urim: "0.2"
generated_at: "2026-10-26T10:00:00-04:00"
compiler: { name: urim, version: 0.2.0 }
integrity: "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
contracts:
  incident-triage:
    version: 1.3.0
    content_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    eval: { dataset_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000", cases: 240 }
    active: typesafe/jev
    standby: [cloudflare/clef-flash]
    selection: strict
    accept_lock_in: []
    targets:
      typesafe/jev:
        camp: systemone
        model: jev
        model_version: "jev-1.14.0"         # PLACEHOLDER
        descriptor: { version: 1.3.0, range: "^1.3.0", hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000" }
        split_strategy: none
        resolution:
          source: explicit
          mode: emulated
          features:
            question_types.choice: native
            question_types.score: native
            question_types.yesno: native
            limits.max_questions_per_request: native
            refusal.typed: { outcome: emulated, via: map_error, declared: prefers }
          extensions: {}
          hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        thresholds:
          page_oncall: { confidence: portable/yes_probability, value: 0.71, method: min_precision_0.95,
                         fitted_for: { contract_version: 1.3.0, model_version: "jev-1.14.0", resolution: "sha256:0000000000000000000000000000000000000000000000000000000000000000" } }
        metrics: { accuracy: 0.912, measured: true }
        plan_report: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
```

**Integrity rule** (from `security/THREAT-MODEL.md` §6.3, adopted under D-14):

> `integrity`: `"sha256-<base64>"` computed over the RFC 8785 canonical JSON of the lockfile's data model with the `integrity` member removed. Writers MUST set it; readers MUST verify it before using any other field except `hoshen`, and MUST refuse a lockfile that fails verification. The integrity hash detects accidental and unreviewed edits; it is not an authorization mechanism.

A lockfile that fails verification is `lock_violation`. The lockfile's data model is the JSON value obtained by reading it under §5.1.1.

**`hoshen` compatibility rule.** `hoshen` increments on every format change that a reader of the previous format would reject or misread. Because lockfile schemas are closed and every key is REQUIRED, adding, removing or retyping any lockfile key is a `hoshen` bump. A tool MUST read `hoshen` before anything else and MUST refuse, with an error naming both versions, to read or write a lockfile whose `hoshen` it does not support. A tool MUST NOT silently rewrite a lockfile to a different `hoshen`; an upgrade happens only through an explicit `apply`.

**Rules.**

1. `resolution` replaces the v0.1 per-target `capabilities` and `polyfills` lists. A reader MUST reject a lockfile in which any target lacks `resolution` or `resolution.hash` (`lock_violation`).
2. **Thummim evaluates exactly the resolved combination.** A Thummim run used by `plan` MUST be keyed by (contract `content_hash`, target id, model version, `descriptor.hash`, `resolution.hash`). `apply` MUST refuse to write a target whose `resolution.hash` differs from the one in the plan report that justified it.
3. If the registry publishes a descriptor outside the locked range, or a change that flips any outcome in `resolution.features` or any extension's schema hash, `plan` MUST fail for that target until it is re-planned; the runtime SHOULD warn but continue serving the locked target.
4. A runtime MUST refuse to call a target that is not in the lockfile, and MUST refuse to apply a threshold whose `fitted_for` does not equal that target's (contract version, model version, `resolution.hash`). Both refusals are `lock_violation`.
5. Failover MAY switch only to a `standby` target that has its own fitted thresholds (§D.2).

See `examples/urim.lock`.

### 6.3 Capability and extension versioning

Three independent version streams. Keeping them separate is the point:

| Event | What changes | Mechanism | Bump |
|---|---|---|---|
| A provider gains, loses or changes a capability | Registry **data** | Drift pipeline PR (§4.3): one issue per drift, an agent PR, a human gate, and two approvals for removals | `descriptor_version` per §4.2 (remove = MAJOR, add = MINOR, correction = PATCH). No contract or spec bump. Locked contracts are affected only through the §6.2 drift rule at the next `plan`. |
| A contract starts using a feature or extension | One **contract** | Author edit, then `plan` and `apply` | Contract **MINOR** (§6.1; a question-type `drop` is MAJOR) |
| An `x-` feature becomes portable core vocabulary | The **spec's** capability vocabulary | Spec PR that defines the capability path, its semantics, its fallbacks, and its registry field | Spec **MINOR** (e.g. `urim: "0.2"` → `"0.3"`) |

**Promotion rule.** An `x-<provider>` feature MAY be promoted to a core capability path when **at least N independent providers** support semantically equivalent behavior, as shown by their registry descriptors (with provenance) and a Thummim conformance fixture that all N pass. Decided (D-11): option A (N = 2 independent vendors) plus a required fallback for the other camp. The options considered (non-normative record):

| Option | Rule | For | Against |
|---|---|---|---|
| A | N = 2 independent vendors | Fast; matches the "two independent implementations" bar of TC39 Stage 4 (two compatible shipping implementations) and the IETF tradition (M; prior-art wording not re-verified today) | Two vendors in the same camp can push camp-specific semantics into core |
| B | N = 2, from **different camps** (`systemone` and `decisions`) | Guarantees the feature isn't one wire format's quirk; camp-aware, like the rest of the spec | Today only OpenAI ships `decisions` natively (§2), so this is effectively an OpenAI veto |
| C | N = 3 independent vendors | More evidence; still achievable given that "at least eight vendors" ship (§1) | Slower; vendor-specific features linger longer as `x-` |
| D | Majority of providers in the registry | Strongest portability claim | Moving target; it shrinks as the registry grows, so features may never promote |

Normative rule (D-11): a promotion requires **two independent vendors**, and the promoted capability definition MUST specify a fallback (`emulate: <name>`, `drop`, or `fail`) for the camp in which no promoting vendor sits, so the promoted feature cannot become a hidden requirement on that camp. "Independent" means not reselling the same model through a gateway (TM X2). If both camps are represented among the promoting vendors, the fallback is still REQUIRED, for any future target that lacks the feature.

Promotion mechanics: the core path gets its own name, and it MUST NOT reuse the `x-` spelling. For one spec MINOR, the compiler SHOULD accept the old `x-<provider>` spelling with a deprecation warning and a mechanical rewrite. If the promoted semantics differ from any vendor's `x-` behavior, that vendor's `x-` key stays as it is, and moving to the core path is a contract MINOR (behavior can change).

---

## Part D — Runtime behavior

Part D defines what every runtime (§2: a future Urim Runtime, Jev Harness, a generated client, or an adapter integration) MUST surface and enforce when it executes a compiled, locked call: the error contract (D.1), failover and circuit breaking (D.2), and telemetry (D.3). D.4 is the matching conformance level. Urim has **no runtime client yet**; whether to ship one is deferred to M4. Part D is an **error and behavior contract**: if one runtime conforms to it, any other conforming runtime can replace it without the application's error handling changing. Part D uses letter numbering so that the numbers of §7–§13 stay stable.

### D.1 Error contract

#### D.1.1 Error object

A failed call, or a failed question inside a partially successful call, carries one error object:

```json
{
  "error": {
    "type": "rate_limited",
    "retryable": true,
    "failover_eligible": true,
    "retry_after_s": 12,
    "message": "rate limited by provider (redacted, truncated)",
    "question_ids": ["team", "severity", "page"],
    "contract": { "id": "incident-triage", "version": "1.2.0", "content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000" },
    "target": { "id": "cloudflare/clef-flash", "model_version": "2026-10-01", "role": "standby",
                "resolution_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000" },
    "provider_status": 429,
    "provider_code": "TODO(vendor-fact): verbatim vendor error code, if any",
    "provider_request_id": "TODO(vendor-fact): verbatim, if the provider returns one",
    "attempt": 2
  }
}
```

| Field | Req. | Meaning |
|---|---|---|
| `type` | MUST | One value from §D.1.2. It is low-cardinality and is also emitted as OTel `error.type` (§D.3). |
| `retryable` | MUST | Whether retrying **the same target** with the same request can succeed. For a given `type` it is fixed by §D.1.2 unless the table says "per response". |
| `failover_eligible` | MUST | Whether §D.2 may move to a standby. This is kept separate from `retryable` on purpose: an `auth` error is not retryable on the same target, and the two answers differ by type. |
| `retry_after_s` | MUST when the provider gave one; absent otherwise | Non-negative integer seconds, normalized from HTTP `Retry-After`, which RFC 9110 §10.2.3 allows as either delay-seconds or an HTTP-date (https://www.rfc-editor.org/rfc/rfc9110#field.retry-after). Vendor-specific rate-limit headers are mapped only when the descriptor names them (§D.1.6). A runtime MAY cap the honored value (cap is configuration). |
| `message` | MUST | Human-readable, **redacted and bounded** (§D.1.5). It is not stable API: never branch on it. |
| `question_ids` | MUST | The questions this error covers (all of them for a whole-call failure). |
| `contract` | MUST | `id`, `version`, `content_hash` from the lockfile entry that was executing. |
| `target` | MUST, except absent for `invalid_contract` | The **lockfile** target id (canonical format is §13 item 4), the locked `model_version`, `role` (`active` or `standby`), and `resolution_hash` (§6.2). |
| `provider_status` | MUST when the transport delivered one; absent otherwise | Verbatim status from the transport: the HTTP status code, or the adapter's own status. It is kept as delivered and never re-mapped (principle 3). Same name as in v0.1. |
| `provider_code` | MAY; absent when not provided | Verbatim vendor error code or type string, if the response carries one. Bounded and escaped (§D.1.5). |
| `provider_request_id` | MUST when the provider returns one; absent otherwise | The vendor's request or trace id, taken from the location the descriptor names (§D.1.6). This is what a vendor's support team will ask for. |
| `attempt` | MUST | 1-based attempt index within this decision call, counting retries and failovers. |

**Absent members.** The error object schema is closed, and an optional member is absent, never `null` (§5.1.2 rule 3).

**Partial success** (unchanged from v0.1): when some questions are answered, the envelope carries `answers` for the successful ones and `answers.<id>.error` for each failed one. A question with an error MUST report `policy.fired: false` (TM N6, N7, and TM §6.1 proposed 14.5). An envelope MUST NOT report `fired: true` for any question whose answer carries an error.

#### D.1.2 Taxonomy

The `type` values are a closed enum: a runtime MUST NOT emit any other value. Types marked *(kept)* existed in v0.1; types marked *(new)* were added in 0.2 and are justified below the table. The failover and breaker columns are normative.

| `type` | When | Typical transport signal (generic HTTP semantics, not vendor facts) | `retryable` | `failover_eligible` | Counts toward breaker (§D.2.3) |
|---|---|---|---|---|---|
| `provider_unavailable` | Provider or network cannot serve: connection refused or reset, DNS or TLS failure, server error | 500, 502, 503; no response | yes (bounded) | yes | yes |
| `rate_limited` | Throttled; may succeed later | 429 (RFC 6585) | yes, after `retry_after_s` if given | yes | no (it sets a cooldown, see §D.2.3) |
| `timeout` | Client deadline exceeded, or the provider reported a timeout | no response within deadline; 408, 504 | yes (bounded; a timed-out request may still be billed) | yes | yes |
| `auth` | Credential missing, invalid, expired, or not permitted for this endpoint | 401, 403; no credential configured | no | **no**, not configurable (D-21) | no |
| `invalid_request` | The provider rejected the compiled request. This indicates compiler, descriptor, or drift error, not caller error. | 400, 404, 413, 422 | no | **no**, not configurable (D-21) | no |
| `capability_unsupported` | At compile or plan time: resolver outcome `unsupported` (§5.9). At runtime: the provider rejected a **locked** feature, for example because of a tier gate or undetected drift (§5.10.6 rule 4). | compile/plan: none; runtime: vendor-specific TODO(vendor-fact) | no | yes (the standby was planned with its own resolution) | yes |
| `response_schema_violation` | The response failed validation against the target's declared **wire** JSON Schema and types (classification rule below, D-19): unparseable, wrong types, unknown or duplicate answer keys, non-finite numbers, over the response size cap, decompression-bomb guard tripped (TM N2, N3, and proposed 14.4) | 2xx with a bad body | no | yes | yes |
| `nonconformant_response` *(kept from v0.1)* | The response is well-typed but violates **contract or DMP semantics**: a label outside the contract's declared options or allowed set for that question, a probability or confidence outside the declared range, a distribution that does not sum to 1 within 0.0001, a chosen key that is not the argmax, an inconsistent `expected_level` | 2xx | no | yes | yes |
| `refused` *(kept)* | The provider's typed refusal, or the `map_error` emulation for refusal (§5.9) | 2xx with a refusal | no | **no** | no |
| `limit_exceeded` *(kept)* | A **local** limit was hit before sending: state `max_bytes`, question count, request count per decision, plan cost budget (TM C7, proposed 14.8). The message MUST name the limit. | none (local) | no | no | no |
| `invalid_contract` *(kept)* | The contract failed to parse, validate, or compile. Compile/load time only; it never comes from a provider. | none | no | no | no |
| `quota_exceeded` *(new)* | Account, billing, or quota exhausted; waiting does not help | vendor-specific: may also arrive as 429. TODO(vendor-fact): descriptor must say how to tell it apart from `rate_limited`. | no | yes | yes (holds the breaker open, see §D.2.3) |
| `lock_violation` *(new)* | The call does not match the lockfile (§6.2). **Local causes:** target not in the lockfile, threshold not fitted for (contract version, model version, resolution), lockfile integrity or `hoshen` check failed, `resolution.hash` missing, or an environment override named an unlocked target. **Response cause (D-19):** the provider reports a model or model version other than the locked one (TM N4, §12 Q9). | local: none; response cause: 2xx | no | **no**, for every cause, not configurable (D-19) | no, for every cause |
| `cancelled` *(new)* | The caller aborted (deadline propagated from the application, or shutdown) | none (local) | no | no | no |
| `internal` *(new)* | A bug in the runtime, target plugin, or adapter. It maps to OTel `_OTHER` only if no better value applies. | none | no | no | no |

Justification for the additions:

- **`quota_exceeded`.** Treating it as `rate_limited` causes retry storms against a provider that will never accept the request, and it pages the wrong owner (billing, not SRE).
- **`lock_violation`.** §6.2 says "MUST refuse" in several places; v0.1 gave the refusal no type. Callers need to tell "your deploy is misconfigured" apart from "the provider is down". A provider silently serving a different model is the same class of problem (the call no longer matches what `plan` evaluated), so it is a `lock_violation` too (D-19). `attempt` and `target` tell the two causes apart. **`lock_violation` is never failover-eligible and never counts toward a breaker, whatever its cause** (D-19, confirmed by David 2026-10-26). Lock drift must stay loud: if a mismatch could fail over, a provider that silently swapped its model would be routed around and the swap would go unseen, and if it counted toward the breaker, the breaker opening would produce the same failover de facto. The runtime abstains and escalates for that decision (§D.2.2), and the mismatch is reported (`error.type`, `gen_ai.response.model`).
- **`cancelled`.** Without it, caller aborts show up as `timeout` and trip breakers and alerts falsely.
- **`internal`.** It keeps runtime bugs out of `provider_unavailable`, which would wrongly blame and fail over away from a healthy provider.

Not added (considered):

- **`network`.** Folded into `provider_unavailable`. The caller's remedy is the same, and keeping it separate would split breaker counts.
- **`content_filtered`.** Treated as `refused` when typed, otherwise as `invalid_request` with `provider_code`. TODO: revisit once descriptors record filter behavior.
- **`model_version_mismatch`.** Folded into `lock_violation` (D-19), not `nonconformant_response`.

Rules:

1. A target plugin MUST map every provider failure to exactly one `type`. A failure it cannot classify MUST become `internal`, never success.
2. Malformed or nonconformant responses MUST fail closed. They MUST NOT be repaired, coerced, or partially trusted (TM N2, N7, and proposed 14.4). `raw` stays untrusted (TM N5).
3. `invalid_contract` and `limit_exceeded` MUST be detected locally, before any network call, whenever the information is available.

#### D.1.3 Classifying a bad response (D-19)

A 2xx response is checked in this fixed order. The first failing check decides the `type`:

1. **Wire schema and types → `response_schema_violation`.** Anything detectable by the target's declared JSON Schema and types: unparseable body, wrong JSON types, missing or duplicate answer keys, non-finite numbers, size cap, decompression guard. "Declared JSON Schema" here means the target's **contract-independent** response schema (from the descriptor or target plugin), not a schema specialized per contract. That keeps classification stable: whether "unknown label" is a schema error must not depend on whether a compiler happened to inline the contract's options as an `enum`.
2. **Lock → `lock_violation`.** The response's reported model or model version differs from the lockfile's.
3. **Contract semantics → `nonconformant_response`.** A well-typed response that breaks the contract or DMP rules.

Required Thummim fixtures (paths TODO, e.g. `thummim/fixtures/errors/classify/`). Values are illustrative and are not vendor facts:

| Fixture | Response (abbreviated) | Expected `type` |
|---|---|---|
| `schema-not-json` | `<html>…` with status 200 | `response_schema_violation` |
| `schema-wrong-type` | `"distribution": {"high": "0.4"}` (string where a number is declared) | `response_schema_violation` |
| `schema-nan` | `"probability": NaN` | `response_schema_violation` |
| `schema-duplicate-key` | two `severity` answers | `response_schema_violation` |
| `semantic-unknown-label` | choice `"team": "payments-xyz"`, not among the contract's options | `nonconformant_response` |
| `semantic-out-of-policy-label` | a declared label that the contract does not allow for this question (exact mechanism depends on the §13 item 3 grammar) | `nonconformant_response` |
| `semantic-confidence-range` | `"confidence": 1.3` where the declared range is [0, 1] | `nonconformant_response` |
| `semantic-distribution-sum` | distribution sums to 0.97 | `nonconformant_response` |
| `semantic-not-argmax` | chosen key is not the highest-probability key | `nonconformant_response` |
| `lock-model-mismatch` | response reports model `jev-1.15.0` (placeholder) while the lock says `jev-1.14.0` (placeholder) | `lock_violation` |
| `order-schema-before-lock` | wrong types **and** a mismatched model | `response_schema_violation` (rule 1 runs first) |

#### D.1.4 Removal of `kind`

**(D-18)** v0.1 named the classifier member `kind`. In protocol 0.2 it is **`type`**, for three reasons: the runtime-behavior draft specifies `type`, it lines up with OTel `error.type`, and the per-answer `type` (`choice`/`score`/`yesno`) lives in a different object, so the names don't collide. In a 0.2 error object, `kind` is an unknown member, and emitting it is non-conformant. (The 0.1 dual-emit rule is recorded in CHANGELOG.md; it applies only to tools still emitting protocol 0.1 envelopes.)

#### D.1.5 Redaction and bounds

These follow TM §4.9 (rules 1–5, a single redaction function) and TM §6.1 (proposed §14.7, "No secrets in artifacts").

1. Every string field in an error object that comes from outside the runtime (`message`, `provider_code`, `provider_request_id`, any detail) MUST pass through the implementation's **single** redaction function before it is stored, logged, returned, or exported.
2. Error objects, spans, metrics, and logs MUST NOT contain credentials, request headers, `state` content, contract `instructions`, or answer content. `raw` MUST NOT include request headers (TM §4.9).
3. `message` MUST be truncated to a bounded length. The PROPOSED default is 512 bytes; this is a design value, not a vendor fact. Strings from the provider MUST be escaped for C0/C1 control, bidi, and zero-width characters (TM P5). Provider error bodies can echo input, so implementations SHOULD prefer a fixed message per `type` plus `provider_code` over provider text.
4. `provider_request_id` and `provider_code` MUST be bounded (PROPOSED 256 bytes) and escaped. They are high-cardinality, so they go on spans and errors only and MUST NOT be used as metric attributes.
5. URLs in errors or telemetry MUST be reduced to scheme + host + port (`server.address`/`server.port`). Path and query MUST NOT be recorded by default.
6. The verbatim provider error body MAY be kept in `raw` under the existing `raw` retention rule (§5.7: retained during `plan`, optional in production). It remains untrusted and redacted.

#### D.1.6 Where the provider mapping lives

**(D-28) Error mappings live in the registry.** The mapping from vendor signals to `type`, the request-id location, the retry-hint headers, and how to tell `quota_exceeded` apart from `rate_limited` are **vendor facts**. They belong in descriptors, not in the spec and not in plugin code. That is consistent with SPEC.md's closing line ("belong in descriptors, not in the spec").

Proposed descriptor field group (all PROPOSED, all values TODO(vendor-fact) until sourced with provenance through the §4.3 pipeline):

```yaml
# <vendor>.provider.yaml (fragment) — PROPOSED field group; no values asserted
errors:
  request_id: { from: header, name: TODO(vendor-fact) }     # or: from: body, path: TODO
  retry_hints: [ { header: Retry-After, format: rfc9110 } ] # plus vendor headers only if documented: TODO(vendor-fact)
  map:                                                      # vendor signal -> Urim error type; generic HTTP fallback applies otherwise
    - { when: { status: 429, code: TODO(vendor-fact) }, type: quota_exceeded }
  provenance: { source: TODO, checked: TODO }
```

Absent a descriptor mapping, a plugin MUST apply the generic HTTP column of §D.1.2. A target plugin MUST NOT hard-code vendor-specific mappings. Drift in `errors` is ordinary registry drift (§4.3), and the descriptor hash in the lockfile pins the mapping that `plan` saw.

---

### D.2 Failover and circuit breaking

#### D.2.1 Eligibility

1. A runtime MAY fail over **only** to targets listed in the lockfile's `standby` for that contract, in lockfile order. Each MUST have a `plan_report`, thresholds fitted for (contract version, model version, `resolution.hash`) (§6.2), and a descriptor within its locked range. Nothing else qualifies: no registry lookup, no `targets_query` evaluation, and no "similar model" at runtime (TM R2, R3).
2. On the answering target, **that target's** fitted thresholds apply (principle 4). The envelope `target` MUST be the target that answered, and `policy.source` MUST stay `lock`.
3. Failover MUST be triggered only by an error with `failover_eligible: true`. `refused` MUST NOT trigger failover: shopping for a model that doesn't refuse is a policy bypass. `auth` and `invalid_request` MUST NOT trigger failover, and a runtime MUST NOT offer configuration that makes them eligible (D-21).
4. **Architecture invariant (D-27).** Failover is **whole-request**: answers from two targets MUST NOT be merged into one envelope. A runtime MUST NOT **hedge** (send the same decision to more than one target concurrently). Hedging multiplies cost (TM C7) and sends `state` to an additional provider.
5. Neither hedging nor per-question failover may be offered before M4. From M4, either MAY be offered only behind an explicit lockfile key (names TODO), which `plan` evaluates and `apply` writes like any other resolution input. With the key absent, both remain forbidden. No environment variable, runtime flag, or SDK option may enable them. Owners (confirmed by David, 2026-10-26): the Architecture Agent and the runtime-behavior (Part D) agent jointly hold this invariant; neither may relax it alone (`drafts/DECISIONS.md`, D-27).
6. Retries and failovers share one per-decision budget: maximum attempts and a total deadline. The PROPOSED attempt default is `1 + retries + len(standby)`. The deadline and retry counts are configuration; this specification asserts no values.
7. **Adapters (amends §5.6).** Adapter-level failover (e.g. a gateway retrying on a backup model) MUST be disabled, unless the adapter reports which model answered and that model is a locked target. Otherwise the answering model is unplanned (TM X2, N4). This is the §5.6 MUST (D-26).

#### D.2.2 Exhaustion: abstain and escalate

If no eligible target remains, or the budget is spent, the runtime MUST return an envelope in which:

- every affected question has `policy.fired: false`, an `error` (the last attempt's `type`), and `failover: { exhausted: true, attempts: n }`;
- the decision is marked **abstained**, and the action reported is the rule's **escalation** action.

**(D-22)** Default: *abstain and escalate*. Each policy rule MAY declare its escalation action with a per-rule key `on_error:` (key name PROPOSED). If `on_error` is absent, the runtime returns a generic `escalate` signal for the application to handle. The rule's `else` is **never** implicit: it is used on error only if `on_error` names that action explicitly, in which case the author has made the choice on the record.

The contract example shows why the default cannot be `else`. In `incident-triage`, `page_oncall.else` is `queue_for_business_hours`. Falling back to that during a provider outage would quietly not page anyone.

#### D.2.3 Circuit breaker

1. A runtime that fails over SHOULD keep a breaker **per lockfile target id**, with states `closed`, `open`, and `half_open`. Thresholds, windows, and probe policy are configuration (M4); this specification asserts no defaults.
2. These count toward opening: `provider_unavailable`, `timeout`, `response_schema_violation`, `nonconformant_response`, and runtime `capability_unsupported`. `quota_exceeded` opens the breaker and holds it open until configuration changes or an operator resets it. `rate_limited` puts the target in a cooldown until `retry_after_s` without counting as a failure. `auth`, `invalid_request`, `refused`, `limit_exceeded`, `cancelled`, and `internal` MUST NOT count, because they say nothing about provider health. `lock_violation` MUST NOT count, whatever its cause (D-19): an opened breaker would move traffic to a standby, which is the failover that §D.1.2 forbids for lock drift.
3. An open breaker on the `active` target makes the runtime skip to standby per §D.2.1. That skip MUST be emitted as a failover event (§D.3.4) with the reason `circuit_open`.
4. Breaker state is local to the process. Sharing it across instances is the application's business. Core MUST NOT phone home (TM X3).
5. Breaker state MUST be observable as a metric (§D.3.3).

#### D.2.4 Provider status pages

Status pages MAY be used as an **optional health signal only**:

- A status-page input MAY deprioritize a locked target or pre-open its breaker. It MUST NOT add a target, MUST NOT override §D.2.1, and MUST NOT block or delay a call when the status page is slow, unreachable, or malformed.
- Fetching status pages MUST NOT be part of the core runtime. TM X3 limits core network calls to the locked endpoint. It is a separate, opt-in plugin or an application-supplied hook.
- Status-page URLs and formats are vendor facts (TODO(vendor-fact)). If recorded, they go in descriptors as informational fields.

---

### D.3 Telemetry (OpenTelemetry mapping)

#### D.3.1 Status of the upstream conventions (verified 2026-10-26)

- The OTel GenAI semantic conventions **moved** out of the core repo into https://github.com/open-telemetry/semantic-conventions-genai (PR https://github.com/open-telemetry/semantic-conventions/pull/3696, merged 2026-05-05). Core **v1.42.0** (2026-06-12) **deprecated** the `gen_ai.*` definitions in core. The latest core release is **v1.44.0**, published 2026-08-04 20:00:58 UTC (16:00 EDT). Sources: https://github.com/open-telemetry/semantic-conventions/releases (GitHub API, read 2026-10-26) and https://explorer.opentelemetry.io/agent/semantic-conventions/genai.md.
- The new repo had **no release or tag** on 2026-10-26. All citations below are pinned to commit `20259355b9631e3f032dcc099d1b5a2666818c42` (committed 2026-10-26 00:55 EDT). Repo issue #247 advises staying on the deprecated core constants until a release exists.
- Everything `gen_ai.*` is **Development** stability. `error.type`, `server.address`, `server.port`, and `http.response.status_code` are **Stable** (core v1.44.0 registry).

**Normative consequence (D-25):** the `gen_ai.*` mapping is **informative** until semconv-genai publishes a release, and is then **pinned** to that release. The drift pipeline opens the pin-bump PR when upstream releases; David approves it. The `urim.*` names, the error `type` values, and the rule "telemetry off by default, no phone-home" are normative now.

**Where the mapping lives (D-23 as replaced):** the attribute and metric names below are the content of a **separately versioned Urim telemetry mapping** (§D.3.6). This section keeps the semantics. The mapping artifact and its full design record are `drafts/SPEC-telemetry-contract.md` until the data file exists; where a name below and the mapping disagree, the mapping wins.

#### D.3.2 Emission rules

1. Telemetry is **off by default**. It is emitted only through the OpenTelemetry API that the application configures (its own SDK and exporter). Core MUST NOT bundle an exporter or a default endpoint (TM X3).
2. §D.1.5 applies in full. `state`, `instructions`, answers, distributions, and `raw` MUST NOT be recorded by default. Content capture, if offered, MUST be an explicit opt-in. It mirrors the GenAI conventions' own Opt-In content attributes and still passes through redaction.
3. A per-question `refused` is an answer, not a request failure. It MUST NOT set span status `Error` or `error.type` on the inference span (this matches upstream PR #596, which records refusal as a result type distinct from request failure). It is counted by the mapping's refusal metric.
4. Errors are recorded per *Recording errors* (core v1.44.0, `docs/general/recording-errors.md`). A failed attempt's span gets status `Error` and `error.type`. "Errors that were retried or handled (allowing an operation to complete gracefully) SHOULD NOT be recorded on spans or metrics that describe this operation." So a decision that succeeded after a failover leaves the parent span's status unset and has no `error.type`. The failed child attempt carries both.

#### D.3.3 Spans, attributes and metrics

**Spans.**

- **Parent span (PROPOSED).** One per decision call. Name: `urim.decide {contract id}`. Kind: INTERNAL.
- **Child span.** One GenAI client inference span per provider request **per target**. Same-target retries are inside that span, because upstream defines the inference span as the logical operation "with all retries" (`gen-ai-spans.md`; see also open PR #562). A failover to another target starts a new inference span, and so does each split request when the `split` emulation is active. It follows the GenAI client inference span (`docs/gen-ai/client-inference.md`, Development):
  - kind SHOULD be CLIENT;
  - name SHOULD be `{gen_ai.operation.name} {gen_ai.request.model}`.

| Attribute | Where | OTel requirement / stability | Urim value |
|---|---|---|---|
| `gen_ai.operation.name` | child | Required / Development | No well-known value exists at the pinned commit. Open upstream PR #596 proposes **`decision`**, on the inference span. The telemetry mapping (§D.3.6) adopts `decision` and no longer proposes `decide`. |
| `gen_ai.provider.name` | child | Required / Development | A well-known value where one applies (the list includes e.g. `openai`, `perplexity`, `azure.ai.openai`). Otherwise a custom value equal to the target id's provider segment. At the pinned commit the list has `openai` but no TypeSafe or Cloudflare value. |
| `gen_ai.request.model` | child | Conditionally Required / Development | The **locked** model version from the lockfile |
| `gen_ai.response.model` | child | Recommended / Development | The model the provider reports, if any. A mismatch with `gen_ai.request.model` is the N4 signal. |
| `gen_ai.response.id` | child | Recommended / Development | The provider's response id, if the body carries one |
| `gen_ai.usage.input_tokens` (and output) | child | Recommended / Development | Only if the provider reports tokens; never estimated |
| `error.type` | child on failure; parent only if the decision failed overall | Conditionally Required / **Stable** | The Urim error `type` (§D.1.2). This is the "documented list of errors" the convention asks instrumentations to publish. `_OTHER` is used only for `internal` when nothing better fits. |
| `server.address` / `server.port` | child | Recommended, Conditionally Required / **Stable** | Host and port of the locked endpoint only |
| `http.response.status_code` | child, HTTP targets | **Stable** (core registry) | Same as `provider_status` |
| `urim.contract.id`, `urim.contract.version` | both | Decided (D-24) | From the lockfile |
| `gen_ai.prompt.name`, `gen_ai.prompt.version` | child | Conditionally Required / Development | Decided (D-24): the contract id and the contract version, set **in addition to** `urim.contract.*` |
| `urim.target.id`, `urim.target.role` | both | PROPOSED | Lockfile target id; `active` or `standby` |
| `urim.resolution.mode` | child | PROPOSED | `exact`, `emulated`, or `degraded` (§6.2) |
| `urim.attempt` | child | PROPOSED | Index of the final attempt in this span. Same-target retries share one inference span, so this is the retry count + 1. |
| `urim.provider.request_id` | child (spans only) | PROPOSED | `provider_request_id`; high-cardinality, so never a metric attribute |
| `urim.request_hash` | child (spans only) | PROPOSED | §5.7 `request_hash` (TM C8) |
| `urim.decision.outcome` | parent | PROPOSED | `answered`, `partial`, `abstained`, or `failed` |

**Why `gen_ai.prompt.*` carries the contract (D-24 rationale).** The contract id and version identify the versioned artifact that produced the request, which is what `gen_ai.prompt.name` and `gen_ai.prompt.version` describe, so the mapping is consistent with the `prompt.*` meaning. It does not cover per-question names. Open upstream PR #596 (https://github.com/open-telemetry/semantic-conventions-genai/pull/596), in `docs/gen-ai/non-normative/decision-models-design.md`, section "Existing fields and their limits" (https://github.com/open-telemetry/semantic-conventions-genai/blob/62786c0eae29f7dbc21f1bcf484e84ff435f8be2/docs%2Fgen-ai%2Fnon-normative%2Fdecision-models-design.md), has this row in its table (columns "Existing convention | Reusable meaning | Boundary for decisions"):

> | `gen_ai.prompt.name`, `gen_ai.prompt.version` | An observable named/versioned prompt template. | Arbitrary question names are not prompt or rubric versions. |

Urim therefore expects upstream to carry per-question and per-result names under a decision-specific namespace (#596 proposes `gen_ai.decision.results`, with a `question_name` member), and keeps its own per-question data under `urim.*` until then. This is an inference from an open PR. It MUST be re-verified when #596 merges, and any change goes through a mapping bump (§D.3.6).

**Namespace choice.** Core naming guidance (v1.44.0 `docs/general/naming.md`) recommends a company reverse-domain prefix, or a reasonably unique application-name prefix, for non-OTel names. It also says not to reuse an existing OTel namespace. The prefix `urim.` follows the application-name option (D-24). `gen_ai.*` MUST NOT be extended with Urim-specific names; names go upstream only through an accepted semconv-genai change.

**Metrics.**

| Metric | Instrument / unit | Status | Attributes (low-cardinality only) |
|---|---|---|---|
| `gen_ai.client.inference.duration` | Histogram, `s` | Development (`client-inference.md`); buckets as specified there | `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `error.type` (on failure), `server.address` |
| `gen_ai.client.inference.usage.input_tokens` / `.output_tokens` | per `gen-ai-token-metrics.md` | Development | Only if the provider reports tokens |
| `urim.decision.duration` | Histogram, `s` | PROPOSED | End-to-end, including retries and failover. Attributes: `urim.contract.id`, `urim.decision.outcome`, `error.type` (on failure) |
| `urim.failover.count` | Counter, `{failover}` | PROPOSED | `urim.contract.id`, `urim.failover.from`, `urim.failover.to`, `error.type` (or `circuit_open`) |
| `urim.circuit_breaker.state` | Gauge or UpDownCounter, `1` (0/1 per state) | PROPOSED | `urim.target.id`, `urim.circuit_breaker.state` = `closed`, `open`, or `half_open`. One series per state, so an alert can watch `open == 1`. |
| `urim.decision.abstained.count` | Counter, `{decision}` | PROPOSED | `urim.contract.id`, policy rule id, `error.type` |

Duration metric: upstream PR #521 (merged 2026-10-06 15:58 EDT) made `gen_ai.client.inference.duration` replace `gen_ai.client.operation.duration` for inference, and open PR #596 places `decision` on the inference span with that metric. A decision is therefore an inference operation and uses `gen_ai.client.inference.duration`. The mapping version pins this (§D.3.6).

#### D.3.4 Events

- **Failover.** Emitted for every failover and every breaker-driven skip. PROPOSED name `urim.failover`, attached to the parent span as a span event or emitted as a log-based event, depending on the implementation's OTel version. Attributes: `urim.failover.from`, `urim.failover.to`, `error.type` (or `circuit_open`), `urim.attempt`. On exhaustion: `urim.failover.exhausted = true`.
- **Breaker transition.** PROPOSED name `urim.circuit_breaker.transition`. Attributes: `urim.target.id`, previous and new state, and the triggering `error.type`.
- **Target selection.** `urim.target.selected`, emitted when `selection: available` skips a target that has no credential (§5.10.6). Attributes: `urim.target.id`, `urim.target.skip_reason`.
- The GenAI repo also defines a Development "client operation exception" event (`gen-ai-exceptions.md`). Implementations MAY emit it in addition; it does not replace `error.type`.

#### D.3.5 Envelope addition

Successful envelopes after a failover MUST say so (TM N4, X2):

```json
{
  "urim": "0.2",
  "contract": "incident-triage@1.3.0",
  "target": { "id": "cloudflare/clef-flash", "provider": "cloudflare", "model": "clef-flash",
              "model_version": "2026-10-01", "camp": "systemone", "role": "standby" },
  "failover": { "from": "typesafe/jev", "reason": "timeout", "attempts": 2, "exhausted": false },
  "answers": { "page": { "…": "…", "policy": { "threshold": 0.78, "source": "lock", "fired": true } } }
}
```

Here `0.78` is Clef's own fitted `page_oncall` threshold from `examples/urim.lock`, not Jev's `0.71`. That is principle 4 at runtime.

The `failover` object, when not `null`, has exactly these REQUIRED members: `from` (`target-id` of the first target attempted), `reason` (the triggering error `type`, `circuit_open`, or `no_credential` for a `selection: available` skip), `attempts` (`integer` ≥ 1, the §D.1.1 `attempt` count), and `exhausted` (`boolean`). The answering target is the envelope `target`.
#### D.3.6 Telemetry mapping versioning

The names in §D.3.3 and §D.3.4 are the content of the **Urim telemetry mapping**, a separately versioned data file (`telemetry/urim-telemetry-mapping.yaml`, name and path PROPOSED). The design record, data-file shape, dual-emit mechanics, drift pipeline and ownership proposal are in `drafts/SPEC-telemetry-contract.md`. The rules below are normative.

1. **Own version stream.** The mapping has its own SemVer, `mapping_version`, independent of the protocol (`urim`), contract `version`, lockfile format (`hoshen`), descriptors, and packages. A contract MUST NOT name a mapping version, and the mapping version MUST NOT be recorded in the lockfile, so a telemetry rename never invalidates a `plan` or forces a re-`apply`. A runtime MUST record the mapping it used as `urim.telemetry.mapping.version` on the parent decision span.
2. **Pre-1.0 rules (decided by David, 2026-10-26).** The mapping stays at `0.y.z` and follows pre-1.0 SemVer: a **MINOR** bump MAY break (rename, remove, or change the meaning, unit, instrument type or span model of an emitted name); a **PATCH** bump MUST be additive or a fix (a new optional name, a documentation or fixture fix, or a compatibility-row update with no name change). A rename SHOULD still be dual-emitted for one MINOR (old and new name, identical values), so dashboards keep working across one opt-in. A meaning change is never smuggled into a rename: it gets a new name.
3. **The 1.0 gate.** Mapping 1.0.0 is cut only when every OpenTelemetry GenAI attribute, metric and span name that the mapping **actually emits** has reached **Stable** upstream. The gate is that used subset, not all of OpenTelemetry GenAI. Even then, 1.0.0 is cut only with David's approval. From 1.0.0, standard SemVer applies: only a MAJOR may break.
4. **Decoupled from the spec.** Urim protocol and contract 1.0 are **not** blocked on mapping 1.0. The spec can reach 1.0 while the mapping is still 0.x.
5. **Opt-in.** A runtime selects a mapping through runtime configuration only (§7.4: `telemetry.mapping` / `URIM_TELEMETRY_MAPPING`), never through the contract or lockfile. If unset, a package uses its documented default mapping, an exact version named in its release notes.
6. **Only mapped names.** A name not in the selected mapping MUST NOT be emitted. `origin: otel` names MUST exist at the upstream commit or release that the mapping pins (D-25). `gen_ai.*` names that upstream has not accepted MUST NOT be emitted.
7. **Error types.** The mapping's list of `error.type` values MUST equal §D.1.2 for every protocol version it declares.

### D.4 Urim Runtime conformance

A runtime conforms to **Urim Runtime** (§8) if it:

1. returns the §D.1 error object, with a `type` from the closed §D.1.2 enum, for every failure, including per-question failures in a partial success;
2. classifies bad 2xx responses in the §D.1.3 order and passes every §D.1.3 fixture;
3. applies the §D.1.5 redaction and bounds through a single redaction function;
4. fails over only under §D.2.1, never on `auth`, `invalid_request`, `refused` or `lock_violation`, never hedges, never merges answers from two targets, and abstains and escalates under §D.2.2;
5. keeps breakers per §D.2.3 when it fails over, and makes no network call except to locked endpoints (TM X3);
6. executes only lockfile (target, resolution) pairs and never re-runs capability resolution (§5.9, §5.10.6);
7. emits telemetry only through the application's OpenTelemetry API, off by default, under one selected mapping version (§D.3).

Conformance is checked by Thummim fixtures that replay recorded provider failures against a fault-injecting mock target (§8). Fixture paths are TODO.

---

## 7. The `plan` step

`plan` compares the current locked target with a proposed target (or evaluates a new contract version) on the contract's bound eval set, and outputs a diff-style report plus a pass/fail verdict. `apply` writes the lockfile only if `plan` passed. `plan` and `compile` run capability resolution (§5.9); a runtime never does.

### 7.1 Eval binding

```yaml
eval:
  dataset: ./evals/incident-triage.jsonl   # labeled cases: state + expected answers
  dataset_hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  min_cases: 200
  repeats: 3                              # for noise-aware comparisons
  accept: { … }                           # acceptance criteria, see 7.3
```

### 7.2 Metrics

For each question and each target, `plan` MUST compute:

| Metric | Definition |
|---|---|
| Accuracy | Share of cases where the answer matches the label. |
| Brier score and ECE | Calibration of the distribution against labels. |
| **Selective accuracy at equal escalation rate** | Fix the escalation (abstain-to-human) rate *r* from policy; fit each target's threshold so it escalates exactly *r* of cases; compare accuracy on the cases it keeps. This is the headline metric for "how much can we automate safely". |
| Coverage at target accuracy | Inverse view: share automated while meeting a required accuracy. |
| p50 / p95 latency | Measured end to end through the compiled request. |
| Cost per decision | From the descriptor's pricing basis; labeled `estimated` if pricing is stale or self-hosted cost is modeled. |
| Wording sensitivity | Change in answers/distribution under declared paraphrases of `instructions`. |
| Option-order sensitivity | Change under permutations of choice options and question order. |
| Conformance | Share of responses passing DMP response rules (§5.7). |

Sensitivity comparisons MUST be noise-aware: repeated runs, compared against pooled variance, with a confirmation round before reporting a difference (following jevcompat's method).

### 7.3 Threshold fitting and acceptance

- For each policy rule, `plan` fits a per-target threshold on the eval set to meet the rule's stated objective (e.g. `escalation_rate: 0.15` or `min_precision: 0.95`), and writes it to the lockfile.
- The contract's `accept` block declares pass criteria relative to the incumbent or absolute (e.g. `selective_accuracy: ">= incumbent - 0.01"`, `p95_latency_ms: "<= 150"`, `brier: "<= 0.12"`, `conformance: "== 1.0"`).
- `plan` MUST fail if any MUST criterion fails, if the dataset hash changed without a contract PATCH bump, or if `min_cases` is not met.
- Every reported figure MUST be labeled `measured` or `estimated`.
- `plan` evaluates each target **with its resolution** (§6.2): an emulated or dropped feature is part of what was measured, and the fitted thresholds are recorded with `fitted_for` including the resolution hash.

### 7.4 Resolver and CLI flags

This table lists every flag, option, and configuration key that changes how Urim tooling resolves, plans, or runs a contract, with its status and the reason it exists. It is the source for the README's flag section (`drafts/README-flags.md`). A name marked PROPOSED or TODO may change before it ships; "implemented" means it exists in the reference CLI today (urim repo `CONTRACT.md`, verified 2026-10-26).

| Flag or key | Applies to | Status | What it does | Why it exists |
|---|---|---|---|---|
| `--strict-prefers` | `urim compile`, `urim plan` | **Planned** (D-15) | Treats every `prefers` entry's fallback as `fail` for this run. Resolution then fails, with `capability_unsupported`, for each target that would need an `emulate:` or `drop` fallback, and the report lists each (target, capability path) pair. A passing run means every preferred feature resolved `native` on every target. It never edits the contract and never writes or changes the lockfile. | `fail` in a contract is the author's choice for one entry. Operators and CI also need a portability check, "would this contract work without any emulation or dropped feature?", without editing contracts. Being a run flag, not a contract key, it cannot change what is deployed. |
| `--version`, `-V` | `urim` | Implemented | Prints `urim <VERSION>` and exits 0. | Standard tool identification. |
| `--help`, `-h` | `urim` | Implemented | Prints the usage line and exits 0. | Standard usage help. |
| `urim check <file>` | `urim` | Implemented | Checks one file and reports errors in the documented format. | The only subcommand today. It does not yet accept the 0.2 keys (CHANGELOG.md, "Known conflicts"). |
| `urim migrate` | contracts, lockfiles | **Planned**; name TODO (§5.10.4) | Rewrites a v0.1 contract to 0.2 (`urim:` key, `requires`/`prefers` with explicit fallbacks) and a `hoshen: 1` lockfile to `hoshen: 2`. | v0.1 keys are `invalid_contract` in 0.2, and the error names this command, so every user has a mechanical path. |
| `selection` (contract key) | runtime | Defined; `available` PROPOSED (§5.10.6) | `strict` (absent meaning): use `active`, then `standby` only under §D.2. `available`: MAY skip a locked target that has no usable credential. | Credentials may select among planned targets but never unlock an unplanned feature or target. |
| `URIM_TARGET` (env) | runtime | **Planned**; name TODO (§5.10.6) | Pins one target; it MUST name a lockfile target, otherwise `lock_violation`. | Debugging and staged rollouts without editing the lockfile. |
| `telemetry.mapping` (config) / `URIM_TELEMETRY_MAPPING` (env) | runtime | **Planned**; names PROPOSED (§D.3.6) | Selects the telemetry mapping: an exact version, a MINOR line, or `latest`. Unset: the package's documented default. | Telemetry renames must never touch contracts or lockfiles; users opt in to new names. |
| `telemetry.emit_deprecated` (config) | runtime | **Planned**; name PROPOSED (§D.3.6) | `false` turns off dual-emit of deprecated names early. | Avoids doubled metric series for users who have already migrated dashboards. |

Rules:

1. No flag, environment variable, or configuration key may enable hedging, per-question failover, failover on `lock_violation`, or a target or feature outside the lockfile (§D.2.1, §5.10.6).
2. A flag that changes resolution (today only `--strict-prefers`) MUST be printed in the `plan` report header, so a report can be reproduced.
3. Every new flag or key MUST be added to this table, with its reason, in the same change that adds it.


---

## 8. Conformance levels

| Level | A tool conforms if it… |
|---|---|
| **Urim Compile** | validates contracts against the closed schemas (§5.1.2), runs capability resolution (§5.9, §5.10), compiles to ≥ 1 target per camp deterministically, and produces valid envelopes (§5.7). |
| **Urim Lock** | additionally reads and writes `hoshen: 2` lockfiles, verifies `integrity`, and enforces lockfile-only targets, resolutions, and thresholds (§6.2). |
| **Urim Plan** | additionally runs §7 metrics, fits thresholds, supports `--strict-prefers` (§7.4) once it ships, and gates `apply`. |
| **Urim Runtime** | executes locked calls with the Part D error contract, failover and breaker rules, and telemetry (§D.4). Independent of the three levels above. |

A conformance test suite (fixtures: contracts, descriptors, recorded native responses, expected envelopes) ships with the reference implementation. Every check in it MUST be able to fail against a fault-injecting mock target.

---

## 9. Relationship to existing work

Urim sits **above** wire formats and adapters and **beside** benchmarks. It aims to be contributable, not competing.

| Work | What it does | How Urim relates |
|---|---|---|
| **Decision Model Protocol, draft 0.1** (decisionmodelprotocol.io/specification/0.1) | Request/response rules and JSON Schemas for the `systemone`-style exchange; lists shared confidence, version negotiation, capability discovery, a common error envelope, and a conformance suite as open. | Urim adopts DMP's response rules as its conformance check. Its capability descriptor (§4), registered confidence definitions (§5.4), and error contract (§D.1) are candidate proposals for those open items; nothing has been filed. If DMP adopts equivalents, Urim MUST defer to them. |
| **jevcompat** (mandu05.com) | Unofficial 48-requirement spec and test tool for `POST /v1/systemone` servers; proxy that repairs or refuses. | Urim reuses its robustness rule and noise-aware testing method; jevcompat results MAY populate `method: probe` descriptor fields. |
| **sys1bench** (PyPI 0.3.2) | Calibration benchmarks for decision models. | General leaderboards; Urim's `plan` is per-contract, on the user's own labeled data. `plan` MAY reuse sys1bench metric code. |
| **Buf `protoc-gen-jev`** (experimental) | Typed code generation from Protobuf for Jev. | Prior art for M5 codegen; a contract-to-proto bridge is an open question. |
| **Vercel AI SDK `experimental_decide`, AI Gateway `/v1/evaluate`, LiteLLM, OpenRouter, Pydantic AI `DecisionModel`** | Provider adapters and cross-provider calls; native values preserved; no cross-provider calibration promise; limited failover. | Compile targets (§5.6). Urim supplies the contract, lockfile, fitted thresholds, and evidence-gated switching they do not. |
| **TypeSafe Jev** and Jev Harness | Jev defines the `systemone` shape; Jev Harness is an independent demo that compiles typed choice/score/noul questions into Jev requests and keeps the threshold in application code. | Jev Harness is the reference implementation; its threshold-outside-the-model design becomes Urim's policy layer. David built Jev Harness on TypeSafe's Jev; Urim is not affiliated with TypeSafe. |
| **OpenTelemetry GenAI semantic conventions** (`semantic-conventions-genai`, no release yet; open PR #596 proposes a decision operation) | Span, attribute and metric names for GenAI calls, all at Development stability. | Urim's telemetry mapping (§D.3) uses them where they exist and `urim.*` names otherwise, under its own version stream (§D.3.6). |

## 10. MVP milestones

| # | Milestone | Definition of done |
|---|---|---|
| M0 | Schemas | JSON Schemas for contract, descriptor, envelope, lockfile published in-repo; both example contracts validate; 20+ invalid fixtures are rejected with specific errors. |
| M1 | Two-camp compiler | Compiles `incident-triage` to one `systemone` target (Jev or Clef) and one `decisions` target (OpenAI; Perplexity Decider is systemone-shaped, see §2); requests are byte-deterministic; request splitting tested against a mock with a 2-question limit; envelopes pass DMP response rules on recorded fixtures. |
| M2 | Lockfile | `lock` resolves aliases to pinned versions; runtime refuses unlocked targets and unfitted thresholds (tests prove both refusals). |
| M3 | Plan | `plan` on a ≥ 200-case labeled set reports every §7.2 metric for both targets, fits per-target thresholds, and blocks `apply` when a criterion fails (demonstrated with a deliberately degraded mock). Report reproduces within tolerance on rerun. |
| M4 | Reference implementation | Jev Harness runs its incident-triage workflow from the contract file and lockfile instead of hand-built requests, with no change in visible behavior; provider switch demonstrated via `plan` + `apply` only. |
| — | **MVP = M0–M4** | |
| | *Note (0.1.1)* | **OPEN-DECISION (David): M2 vs principle 5.** M2 writes a lockfile before M3's `plan` exists, but §3 principle 5 says no target enters a lockfile without a passing `plan`. Options are an explicit unplanned/bootstrap lock mode, or merging M2 into M3. |
| M5 | Codegen | TypeScript, Python, Go typed clients generated from a contract; round-trip tests. |
| M6 | Adapter targets | AI SDK and LiteLLM adapter targets pass the same envelope fixtures as raw HTTP targets. |
| M7 | Registry | Public descriptor registry for ≥ 6 providers with provenance and a freshness check in CI. |
| M8 | Registry maintenance pipeline (§4.3) | (a) Watcher runs on a schedule for ≥ 6 providers and normalizes docs, OpenAPI, and changelogs into field groups. (b) On a replayed history of ≥ 10 real past source changes, it detects every one that changed a normalized field and raises ≤ 1 false drift per provider per month. (c) Each drift opens exactly one deduplicated issue on GitHub Issues or Linear with old/new values and sources. (d) For ≥ 80% of drifts in the replay set, the agent's draft PR updates the descriptor, bumps `descriptor_version` correctly, updates the resolver adapter where needed, and adds a fixture that fails on the old behavior and passes on the new. (e) Branch protection blocks merge unless conformance and calibration suites pass and a maintainer approves (two for removal, confidence, or license changes); a test PR proves both blocks. (f) A downstream project with a lockfile gets a failing `plan` when a merged descriptor change leaves its capability range. |

*M8 orchestrator (D-35):* Vercel Workflow for now, kept swappable (for example to GitHub Actions). For Urim's own registry, DoD (c)'s board is GitHub Issues, because D-35 keeps pipeline state in GitHub issues and PRs.

## 11. Non-goals

- **Not a new wire protocol.** Urim does not ask providers to change their APIs.
- **Not a model, router, or hosted gateway.** No inference, no traffic brokering, no billing.
- **Not a leaderboard.** `plan` results are per contract and per dataset, not general rankings.
- **No cross-model calibration guarantee.** Portable confidence standardizes the formula, not the meaning; per-model fitting remains required.
- **No certification of vendors.** Conformance levels apply to Urim tooling. Provider conformance is reported, not certified.
- **No endorsement through names.** Third-party product and company names in this document (for example TypeSafe Jev, OpenAI, Cloudflare Clef, LiteLLM, OpenTelemetry) only identify targets and prior work. Their use implies no affiliation, endorsement, partnership or certification. Thummim output says "conformance reported", never "certified". The proposed register of these names is `docs/legal/marks.yaml` (`security/LEGAL-NOTES.md` §10).
- **No generative structured output.** Schema-constrained text generation (e.g. Claude or Gemini structured outputs) is out of scope for 0.2, though it MAY be added as a target type later for baseline comparison.

## 12. Open questions

1. **Camp convergence.** If DMP or a vendor consortium unifies the two camps, does Urim's compiler collapse to one target family? (Desired outcome: yes, and the contract/lock/plan layers remain.)
2. **Portable confidence semantics.** Should Urim define a *calibrated* portable confidence (e.g. per-model isotonic mapping stored in the lockfile), or only formulas?
3. **Split requests vs. shared context.** *Resolved in 0.2:* splitting happens only where the contract declares `emulate: split` (§5.5 rule 3); `atomic` keeps its absent meaning `false`.
4. **Contract-to-proto bridge.** Should contracts compile to Protobuf to reuse `protoc-gen-jev`, or stay JSON Schema-only?
5. **Eval data privacy.** How should `plan` run against hosted providers when eval data is sensitive (e.g. banks)? Options: residency-aware target filtering, local-only `plan` with open-weight models.
6. **Descriptor governance.** Who can merge vendor-submitted descriptor changes, and how are disputes between docs and probes resolved?
7. **Emulation boundaries.** *Largely resolved in 0.2:* every `prefers` entry names its fallback explicitly (§5.10.3), and nothing is emulated implicitly. Open: which `emulate:` strategies the registry should offer for each capability (§5.11).
8. **Experimental types.** *Resolved in 0.2:* experimental types are allowed only when declared in `requires` or `prefers`, with fallback `drop` or `fail` (§5.3).
9. **Version negotiation.** *Reaction resolved in 0.2:* a reported model other than the locked one is a `lock_violation`, never failed over (§D.1.3, D-19). Open: detection when the provider reports nothing (response fingerprinting vs. trusting version headers).

---

## 13. Open decisions reserved for David

These are marked OPEN-DECISION or TODO where they arise. Nothing in 0.2.0-draft decides them. Items settled since 0.1.1 are recorded in CHANGELOG.md and `drafts/DECISIONS.md`, not here.

1. **Camp definition rule:** body vocabulary vs path vs an added gateway camp (§2).
2. **PROPOSED names awaiting confirmation:** the per-rule `on_error` key (§D.2.2), the key that says how a rule treats a dropped (absent) question (D-16, §5.10.3), the migration command (`urim migrate`, §5.10.4), `selection: available` (§5.10.6), `URIM_TARGET`, the telemetry configuration names (§7.4), and the mapping data-file path (§D.3.6).
3. **Grammars:** `policy` block keys and `when` expressions, the `confidence` block, `accept` expressions (including "incumbent" and MUST markers), `targets_query`, constraint operators, `eval.paraphrases`, and the PROPOSED `id` grammar (§5.1.2).
4. **Canonical target-id format:** `provider` + `model` vs a single `vendor/model` id. The envelope (§5.7, §D.3.5) carries both forms until this is decided. *The model-version field name is closed (D-31, 2026-10-26): it is `model_version` everywhere (descriptor `models[]`, lockfile target entry, `fitted_for`, envelope `target`, error object `target`). Only the id format stays open.*
5. **Hash canonicalization** for `content_hash`, `request_hash`, resolution `hash`, and lockfile `integrity` (e.g. RFC 8785 JCS plus a YAML 1.2 normalization rule).
6. **Naming and package/domain claims:** the capability path scheme (`features.` prefix or not), the score-spread confidence names, "System 1" vs "System One", and how and when to claim the `urim` package names and domains. **Decided (D-33, 2026-10-26):** one package, `urim`, on every registry; `thummim` and `hoshen` are internal names and are not claimed. Still open: *when* to claim `urim`. David (2026-10-26, D-29): "we can't claim the package domains until we have shippable version. So we really need to decide the best path forward for this." Facts for that decision, checked read-only on 2026-10-26 (`security/SUPPLY-CHAIN.md` §G): the unscoped name `urim` returned 404 (no public package) on npm, PyPI and crates.io, and so did the JSR scope `@urim`. The npm scope `urim` already exists, with no public packages and an owner we don't know; that matters only if docs or adapters would use `@urim/…`, which they MUST NOT assume. Every one of these registries treats a name held without genuine use as squatting, which is why claiming before there is a shippable version is a problem. Also open: whether optional adapters (TM X1, backlog #21) stay inside `urim` or become separate packages, which D-33 does not settle.
7. **M2 lock-before-plan vs principle 5** (§10).
8. **`applies_to` and named definitions:** bare `applies_to: portable` vs §5.4's named-definition rule, whether a rule may name a definition directly, and the threshold direction when a yes/no rule fires on "no".
9. **D-13 scope:** whether dropping a `prefers` entry or an `x-` extension with `fallback: drop` is a contract MINOR (current reading, §6.1) or MAJOR.
10. **Telemetry:** the supported mapping window size (three MINORs proposed) and whether to create a Telemetry Domain Agent (`drafts/SPEC-telemetry-contract.md` §10).
11. **Threat model adoption:** whether the proposed §14 "Security considerations" (`security/THREAT-MODEL.md` §6.1) becomes normative in a later draft.
12. **Upstream contributions** (OTel GenAI, DMP): each one separately. Nothing has been filed.
13. **Release identity and legal terms** (`security/LEGAL-NOTES.md` §12). **Decided 2026-10-26:** the licence is Apache-2.0 (as in the repo); the public contact email is `hello@davidthomason.dev`; contribution terms are the DCO (D-32); the release is the single package `urim` (D-33); Urim also publishes on **JSR under the scope `@urim`** (David, t53u); the publisher is **David as an individual for now**, with everything kept portable so ownership can move to a company GitHub org and registry accounts later without limitations (D-34). **Still open:** when to claim `urim` (item 6), and the JSR package name inside `@urim` (`@urim/urim` is PROPOSED).

---

*Vendor facts in this draft reflect research on 2026-10-25 and 2026-10-26 and are non-normative. They belong in descriptors, not in the spec, and will change.*
