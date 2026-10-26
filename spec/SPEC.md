# Decision Contract Transpilation Protocol (DCTP) — v0.1.1 draft

| | |
|---|---|
| Status | Working draft 0.1.1 (corrections to 0.1.0; see CHANGELOG.md). Unpublished. Not a claim of adoption or vendor endorsement. |
| Author | David Thomason (github.com/no-complect) |
| Reference implementation | Jev Harness (https://www.jev-harness.dev), an independent demo built on TypeSafe's Jev |
| Working project name | TBD (candidates: Decisionfile, DecideSpec, Verdictform) |
| Date | 2026-10-25 |

The key words MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are used as in RFC 2119.

---

## 1. Summary

Decision models ("System 1" models) take application state plus typed questions and return typed answers with probabilities instead of generated text. As of October 2026, at least eight vendors ship one, in **two incompatible API styles** with **at least four documented ways of calculating `confidence`** (§5.4). Applications that hard-code one provider's request shape and one model's threshold have to be rewritten when prices change, a provider shuts down, or a better model ships.

DCTP describes a decision **once**, in a provider-neutral **contract** file, and:

1. **compiles** it to any supported provider's native request (or to an existing adapter such as the Vercel AI SDK), and normalizes the response into one envelope;
2. **locks** the exact provider, model version, and *per-model fitted thresholds* in a lockfile;
3. **plans** any provider or model change by running the contract's bound eval set and refusing the switch if the new target does not meet the contract's acceptance criteria.

Changing providers then means a config change plus a passing `plan`, not a rewrite.

Design lineage: **Terraform** (declarative config + pluggable providers + `plan`/lock) and **TypeScript** (ship ahead of the standard; adopt one call at a time; compile down to whatever targets actually support).

The protocol has three parts, matching the three problem areas:

| Part | Problem | Artifact |
|---|---|---|
| A. Provider registry | Data mining: what can each provider do, and at what cost? | Provider capability descriptor (`*.provider.yaml`) |
| B. Contract and transpilation | Isomorphic interface handling: one contract, many wire formats | Contract (`*.decision.yaml`), response envelope |
| C. Versioning | Version control: what changed, and is it still safe? | Contract semver, lockfile (`urim.lock`, hoshen format), `plan` report |

## 2. Terminology

- **Decision model / provider** — a service or open-weight model that scores a supplied answer space and returns typed answers without generating them token by token.
- **Camp** — a family of wire formats. v0.1 recognizes two:
  - **`systemone` camp** — TypeSafe's `POST /v1/systemone` body shape (`model`, `state`, `questions` as a map; question types `choice`, `score`, `noul`; choice options in `criteria`). Also used by Cloudflare Clef/Clef-flash, Liquid AI d1 (`/decisions/v1/systemone`), Fastino GLiDE, and many open "Jev-compatible" servers. **Perplexity Decider and Inception Mercury Decide also use this body shape even though they serve it at a `/v1/decisions` path** (docs.perplexity.ai/docs/decisions/quickstart; docs.inceptionlabs.ai/capabilities/decisions, checked 2026-10-25). Microsoft Decision-1 (Foundry) is listed here provisionally; its wire shape is UNVERIFIED. Formalized by DMP draft 0.1.
  - **`decisions` camp** — OpenAI's `POST /v1/decisions` body shape (`model`, `input`/`input_json`, `questions` as an **array** of items with `name`; question types `predicate`, `choice` with `choices[{value,description}]`, `score` with `levels[{label,description}]`; response `answers[]`). As of 2026-10-25 only OpenAI (also on Azure) ships this shape natively; LiteLLM and OpenRouter expose it as gateway routes.
  - Vercel AI Gateway `/v1/evaluate` uses its own vocabulary (yes/no type named `boolean`) and is treated as an adapter target (§5.6).
  - > **OPEN-DECISION (David): camp definition rule.** v0.1.1 classifies by body vocabulary, which is what the prose above already says. Whether the spec should formally define camps by body vocabulary, by path, or add a third `gateway`/`evaluate` camp is not decided.
- **Contract** — a versioned, provider-neutral declaration of state inputs, questions, answer spaces, policy, and eval binding.
- **Target** — a concrete (provider, model, endpoint or adapter) to which a contract compiles.
- **Native confidence** — whatever number the provider returns as `confidence`, with the provider's own definition.
- **Portable confidence** — a confidence value DCTP computes from the returned distribution, using a definition named in the contract (§5.4).
- **Policy** — thresholds and actions that turn probabilities into application behavior. Policy lives in the contract and lockfile, never in the model request.
- **Eval set** — labeled cases bound to a contract and used by `plan`.

## 3. Design principles

1. **Contract first, wire format second.** The contract is the source of truth. Wire formats are compile outputs.
2. **Complement, don't replace.** Existing adapters are valid compile targets (§5.6). DCTP adds the contract, lock, and plan layers they lack.
3. **Never silently re-mean a number.** Native values MUST be preserved verbatim. Anything DCTP derives is labeled as derived, with its definition.
4. **Thresholds are per model, not per contract.** A threshold fitted on one model MUST NOT be assumed valid on another. (Observed: a 0.9 cutoff tuned on Jev kept none of Clef's answers on one test, attributed in 0.1.0 to Clef's confidence being the squared top-two gap. That formula is UNSOURCED (§5.4), but the observation does not depend on it: native confidence definitions differ across vendors either way.)
5. **Switching is gated by evidence.** No target enters a lockfile without a passing `plan` against the contract's eval set.
6. **Incremental adoption.** One call site can adopt DCTP without touching the rest of the application.
7. **Contributable upstream.** Where DCTP overlaps the Decision Model Protocol (DMP), it SHOULD adopt DMP's definitions and offer its additions back (§9).

---

## 4. Part A — Provider registry (data mining)

### 4.1 Capability descriptor

Each target is described by a machine-readable **provider capability descriptor**. A compiler MUST consult the descriptor before emitting a request, and MUST fail at compile time (not at call time) if a contract uses a capability the target lacks, unless the contract permits a declared fallback (§5.9).

Required fields:

| Field | Meaning |
|---|---|
| `id`, `vendor`, `models[]` | Stable identifiers; each model entry has a pinned `version` and optional alias (e.g. `jev-latest`). |
| `camp` | `systemone` \| `decisions` \| `adapter` |
| `endpoint` | Base URL and path template; auth scheme (API key, Entra ID, etc.). |
| `question_types` | Map from DCTP type to native name, e.g. `yesno: noul` (systemone) or `yesno: predicate` (decisions). Unsupported types are omitted. |
| `limits` | `max_questions_per_request`, `min_choice_options`, `max_choice_options`, `score_levels {min,max}`, `max_state_bytes`. |
| `modalities` | `text`, `json`, `image`, `audio`, `video`; each with `status: ga \| experimental` and any required opt-in header. |
| `confidence` | `definition` (one of the registered names in §5.4, or `undocumented`), plus `source` URL. |
| `pricing` | `basis` (`per_request` \| `per_question` \| `per_token` \| `self_hosted`), `unit_price`, `currency`, `as_of`. |
| `residency` | Regions, private networking, data retention statements. |
| `features` | `caching.prompt`, `refusal.typed`, other optional features, each with `status`. |
| `descriptor_version` | Semver of the descriptor itself (§4.2). |
| `weights` | For open-weight models: `license` (SPDX id), `commercial_restrictions` (free text, e.g. revenue caps), `vram_gb_estimate`. |
| `provenance` | For every field group: `source_url`, `retrieved_at`, `method` (`docs` \| `openapi` \| `probe` \| `vendor_submitted`). |

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
4. **Draft a PR.** An agent drafts a pull request that updates the descriptor (with new provenance and a `descriptor_version` bump per §4.2), updates the resolver adapter for that target if needed (§5.9), and adds or updates conformance fixtures that exercise the changed capability (a test that passes on the new behavior and fails on the old).
5. **Gate.** The PR MAY merge only when (a) the DCTP conformance suite passes against recorded fixtures and, where allowed, the live target; (b) the calibration regression suite on a public reference eval set shows no unexplained change beyond tolerance for affected models; and (c) at least one human maintainer approves. Descriptor changes MUST NOT be auto-merged. `capability_removed`, `confidence_definition_changed`, and `license_changed` MUST require two maintainer approvals.
6. **Notify consumers.** On merge, the release notes list the drift class, so `plan` in downstream projects can warn when a locked target's descriptor moved outside the lockfile's capability constraints.

The pipeline MUST NOT contact vendors, post publicly outside the registry's own repository and board, or run probes that a provider's terms prohibit.

---

## 5. Part B — Contract and transpilation (isomorphic interface handling)

### 5.1 Contract file

A contract is YAML (or equivalent JSON) validated by a published JSON Schema (2020-12). Top-level keys:

```yaml
dctp: "0.1"                 # spec version, REQUIRED
contract: incident-triage   # id, REQUIRED, kebab-case
version: 1.2.0              # contract semver, REQUIRED (§6.1)
description: ...
state:                      # typed inputs, REQUIRED
questions:                  # REQUIRED, ordered map, >= 1
policy:                     # thresholds + actions, OPTIONAL but RECOMMENDED
confidence:                 # portable confidence definition, OPTIONAL (default: top_probability)
eval:                       # eval binding + acceptance criteria, REQUIRED for `plan`
targets:                    # candidate targets, OPTIONAL (lockfile decides what is live)
targets_query:              # browserslist-style target selection, OPTIONAL (§5.9)
required_capabilities:      # feature requirements, OPTIONAL (§5.9)
fallbacks:                  # declared polyfills / drops, OPTIONAL (§5.9)
atomic: false               # forbid request splitting, OPTIONAL
```

See `examples/incident-triage.decision.yaml` for a complete file.

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

### 5.2 State

`state` declares named inputs with a type: `string`, `markdown`, `json` (with optional inline JSON Schema), `image`, `audio`, `video`. Fields MAY be marked `required` and MAY carry `max_bytes`. The compiler serializes state into each target's native `state` representation. Modalities not supported by a target are a compile-time error.

### 5.3 Questions

Questions are an **ordered** map from a stable question id to a definition. Every question MUST have `type` and `instructions`.

| DCTP type | Answer space | `systemone` native | `decisions` native |
|---|---|---|---|
| `choice` | `options`: map of key → description, ≥ 1 (≥ 2 RECOMMENDED) | `choice` | `choice` |
| `score` | `levels`: ordered list of descriptions, ≥ 2 | `score` | `score` |
| `yesno` | `yes` / `no` descriptions (either MAY be omitted) | `noul` | `predicate` |
| `box` *(experimental)* | image region | provider-specific (e.g. Jev `box`, experimental, opt-in header) | provider-specific |
| `extract` *(experimental)* | span or value from state | provider-specific (e.g. Inception Mercury Decide `extract`: 1–26 named fields, returns spans) | provider-specific |

Rules:

- Question ids MUST be stable across contract versions; renaming one is a breaking change (§6.1).
- Option keys MUST be stable identifiers, distinct from display descriptions, so code and policy can refer to them.
- Experimental types MUST NOT be used in a contract unless every locked target declares support; there is no portable fallback.
  > **OPEN-DECISION (David): box/experimental fallback rule.** This rule conflicts with §5.9 and `examples/kyc-document-check.decision.yaml`, which declare `fallbacks.question_types.box: drop_question`. One of the two must change. Left unresolved in 0.1.1.
- In YAML, the `yes`/`no` keys and values MUST be quoted (`"yes"`), because YAML 1.1 parsers read bare `yes`/`no` as booleans. Contract parsers MUST use YAML 1.2 core schema or reject boolean keys.
- `instructions` MAY be a string or a structured object; compilers MUST serialize it into the form each target accepts.
- A `choice` with fewer options than the target's `min_choice_options` MUST be rejected at compile time. OpenAI Decisions and Workers AI Clef require at least 2, so a one-option choice cannot compile for them. The contract-level minimum stays ≥ 1 in 0.1.1.

### 5.4 Confidence

DCTP never redefines a provider's `confidence`. It adds an optional, declared **portable confidence** computed client-side from the returned distribution. v0.1 registers these definitions:

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

1. Map each DCTP question type to the target's native type using its descriptor (`yesno` → `noul` or `predicate`).
2. Map option keys and score levels into the target's native criteria structure, preserving key identity and level order.
3. **Split** the question set into multiple requests if it exceeds `max_questions_per_request`, and merge the answers, preserving question order. If the contract sets `atomic: true`, splitting is a compile error instead.
4. Reject (at compile time) any `choice` with fewer than `min_choice_options` or more than `max_choice_options` options, or any `score` outside `score_levels`.
5. Never include policy or thresholds in the request.
6. Emit a deterministic request: the same contract, state, and target MUST produce byte-identical request bodies (excluding auth and request ids), so requests can be hashed into the lockfile and replayed.
7. Record the compiled request hash in the response envelope.

Splitting changes encoder context on some servers (jevcompat reportedly observed one server whose answer moved from 0.768 to 0.351 when question order was reversed; this figure is UNVERIFIED and was not located in jevcompat's public docs on 2026-10-25). `plan` therefore measures order sensitivity (§7), and a lockfile entry SHOULD record the split strategy it was evaluated with.

### 5.6 Adapters as compile targets

A target with `camp: adapter` compiles to a call into an existing library rather than raw HTTP. v0.1 names these adapter targets (exact call shapes are defined by each adapter's documentation and owned by its target plugin):

- Vercel AI SDK `experimental_decide` and AI Gateway `/v1/evaluate` (yes/no type named `boolean`)
- LiteLLM decisions
- OpenRouter
- Pydantic AI `DecisionModel`

When compiling to an adapter, the adapter's own response normalization MUST be preserved in `raw`, and DCTP's envelope is built on top of it. Adapter-level failover (e.g. AI Gateway's single low-confidence retry on a backup model) SHOULD be disabled or recorded in metadata, because it can change the answering model without a `plan`.

### 5.7 Normalized response envelope

Every call returns one envelope regardless of target:

```json
{
  "dctp": "0.1",
  "contract": "incident-triage@1.2.0",
  "target": { "provider": "cloudflare", "model": "clef-flash", "version": "2026-10-01", "camp": "systemone" },
  "request_hash": "sha256:…",
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
  "usage": { "latency_ms": 41, "cost": { "amount": 0.00012, "currency": "USD", "basis": "per_token", "estimated": true } },
  "raw": { "…": "native response, verbatim" }
}
```

Envelope rules:

- *Example notes (0.1.1):* values match `examples/urim.lock`. `native` is null because Clef returns no confidence for `noul` answers. `version` "2026-10-01" is a PLACEHOLDER (see §4.1 on pinning). Cost is `estimated` because the example descriptor's pricing is not yet filled. **OPEN-DECISION (David): canonical target-id format** (`provider`+`model` vs a single `vendor/model` id as used in contracts and lockfiles).
- `confidence.native` MUST be `null` when the provider returns no native confidence, for example for `noul` on Jev, Clef or Perplexity, or OpenAI `predicate`.

- `distribution` MUST use contract option keys (choice), `yes`/`no` (yesno), or zero-based level indices as strings (score), and MUST sum to 1 within 0.0001 after the compiler's mapping. For `score`, the envelope MUST also include `expected_level` (probability-weighted index), consistent with DMP. It is computed from `distribution` and never copied from the native `score` field, because native score semantics differ: Jev, Clef and Inception return the probability-weighted level, while Fastino GLiDE returns the argmax level and reports the expectation separately as `expected_level`.
- `raw` MUST contain the unmodified native response (MAY be omitted in production by configuration, but MUST be retained during `plan`).
- `policy` is computed by the DCTP runtime from the lockfile, not by the provider.

**Error envelope.** Failures return `{ "error": { "kind", "retryable", "provider_status", "message", "question_ids" } }` where `kind` is one of `invalid_contract`, `capability_unsupported`, `limit_exceeded`, `auth`, `rate_limited`, `provider_unavailable`, `refused`, `nonconformant_response`. `nonconformant_response` MUST be raised (not silently repaired) when a provider response violates DMP response rules, e.g. a distribution that does not sum to 1 or a chosen key that is not the argmax. Partial success (some questions answered) MUST be reported per question.

### 5.8 Typed codegen (later milestone)

From a contract, generators SHOULD emit typed clients for TypeScript, Python, and Go: a state input type, a result type with option keys as literal unions/enums, and a `decide()` function returning the envelope. Codegen is out of scope for MVP (§10, M5) and SHOULD reuse Buf's `protoc-gen-jev` and Pydantic AI type models where practical.

### 5.9 Capability-gated resolver

A contract feature is available to code **only** when every target it may run on supports it. The resolver enforces this at **compile time** and again at **plan time** (against the descriptor version being locked), never first at call time.

Prior art: Terraform's provider schemas and `required_providers` block (declare the providers and version ranges you depend on; the tool refuses configurations the provider schema does not accept), and browserslist + Babel `preset-env` + caniuse (declare targets once; the compiler enables, transforms, or polyfills each feature according to a capability table).

**Declaring targets and requirements.** A contract MAY declare:

```yaml
required_capabilities:          # like required_providers, but per feature
  modalities.image: ">= ga"     # or "experimental" to opt in
  question_types.box: optional  # used only if available; see fallbacks
  limits.max_questions_per_request: ">= 3"
  residency.regions: { includes: [us] }
  caching.prompt: optional
  refusal.typed: required
targets_query: "camp:any, residency:us, license:apache-2.0 | hosted, not experimental"   # browserslist-style
fallbacks:
  question_types.box: drop_question          # or: error (default)
  limits.max_questions_per_request: split    # or: error, if atomic
  caching.prompt: ignore
  refusal.typed: map_error                   # map provider refusal to error.kind=refused
```

**Gated features (v0.1 set):** non-text modalities (`image`, `audio`, `video`); experimental question types (`box`, `extract`); typed refusal; question count above a target's limit; choice size and score levels above limits; prompt/state caching; data residency and private networking; open-weight license constraints.

**Resolution rules.**

1. The resolver evaluates `targets_query` against the registry to produce the candidate target set, then intersects it with any explicit `targets`.
2. For each feature the contract uses and each candidate target, the resolver looks up the descriptor. Outcome is one of: `native` (supported), `polyfill` (a declared fallback can emulate it, e.g. `split` for question limits, or `map_error` for refusal), `dropped` (declared `drop_question`/`ignore`), or `unsupported`.
3. `unsupported` on any `required` feature MUST fail with an error naming the feature, the target, the descriptor version and its source URL, and the fallbacks that would make it compile. Example: `capability_unsupported: question_types.box is not supported by clef-flash (descriptor 1.4.0, source …); declare fallbacks.question_types.box or remove the target.`
4. A `polyfill` MUST be a documented, deterministic transform with known effects. Polyfills that change decision behavior (such as `split`, which changes shared context) MUST be evaluated by `plan` with the polyfill active, and the lockfile records which polyfills were active.
5. Generated typed clients (§5.8) MUST expose an optional or dropped feature as optional in the type (e.g. `box?: Box`), so code cannot assume it exists on every target.
6. The resolver MUST emit a capability report (feature × target matrix with the outcome) as part of `compile` and `plan` output, like a caniuse table for the contract.

---

## 6. Part C — Version control

### 6.1 Contract semver

| Change | Bump |
|---|---|
| Rename or remove a question, option key, or state field; change a question's type; reorder or remove score levels; change `atomic` | **MAJOR** |
| Add a question; add an option to a `choice`; add an optional state field; change `instructions` or option descriptions; change portable confidence definition | **MINOR** |
| Edit metadata, description, eval set additions that do not change acceptance criteria | **PATCH** |

Any MINOR or MAJOR change MUST invalidate every lockfile entry's fitted thresholds for that contract and require a new `plan`. Wording changes are MINOR, not PATCH, because decision models are measurably sensitive to wording.

### 6.2 Lockfile (hoshen format)

The hoshen is the lockfile format: it holds what was decided and measured, so a verdict can be reproduced. The lockfile is named `urim.lock`. It is generated by `plan`/`apply` and SHOULD be committed. It is the **only** source of live targets and thresholds.

Top-level fields:

| Field | Meaning |
|---|---|
| `hoshen` | Integer format version of the lockfile itself (currently `1`). See the compatibility rule below. |
| `urim` | Version of the protocol the lockfile was generated against (currently `"0.1"`). |
| `generated_at` | RFC 3339 timestamp of the `apply` that wrote the file. |
| `compiler` | `{ name, version }` of the tool that wrote the file (e.g. `{ name: urim, version: 0.1.0 }`). |
| `contracts` | Map of contract id → per-contract entry (below). |

**`hoshen` compatibility rule.** `hoshen` increments only on breaking format changes. Adding optional fields does not bump it. A tool MUST read `hoshen` before anything else and MUST refuse, with an error naming both versions, to read or write a lockfile whose `hoshen` it does not support. A tool MUST NOT silently rewrite a lockfile to a different `hoshen`; an upgrade happens only through an explicit `apply`.

For each contract it records:

- `contract` id, `version`, and `content_hash`.
- `active` target and an ordered list of `standby` targets (eligible for failover).
- Per target: `provider`, `model`, pinned `version` (aliases such as `jev-latest` MUST be resolved to a concrete version), `descriptor_hash`, `compiler_version`, split strategy.
- Per target, per policy rule: the **fitted threshold**, which confidence it applies to, the fitting method, and the metrics at that threshold.
- `eval` dataset hash and the `plan` report hash that justified the entry.
- Per target, **capability constraints**: the `descriptor_version` resolved at lock time, a semver range of acceptable descriptor versions (default `^` of the locked version), the capability outcomes (`native`/`polyfill`/`dropped`) from §5.9, and the active polyfills.

If the registry publishes a descriptor outside the locked range, or a change that flips any locked outcome, `plan` MUST fail for that target until it is re-planned; the runtime SHOULD warn but continue serving the locked target.

A runtime MUST refuse to call a target that is not in the lockfile, and MUST refuse to apply a threshold not fitted for that exact (contract version, model version). Failover MAY switch only to a `standby` target that has its own fitted thresholds.

See `examples/urim.lock`.

---

## 7. The `plan` step

`plan` compares the current locked target with a proposed target (or evaluates a new contract version) on the contract's bound eval set, and outputs a diff-style report plus a pass/fail verdict. `apply` writes the lockfile only if `plan` passed.

### 7.1 Eval binding

```yaml
eval:
  dataset: ./evals/incident-triage.jsonl   # labeled cases: state + expected answers
  dataset_hash: sha256:…
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

---

## 8. Conformance levels

| Level | A tool conforms if it… |
|---|---|
| **DCTP-Compile** | validates contracts against the schema, compiles to ≥ 1 target per camp deterministically, and produces valid envelopes. |
| **DCTP-Lock** | additionally reads/writes lockfiles and enforces lockfile-only targets and thresholds. |
| **DCTP-Plan** | additionally runs §7 metrics, fits thresholds, and gates `apply`. |

A conformance test suite (fixtures: contracts, descriptors, recorded native responses, expected envelopes) ships with the reference implementation. Every check in it MUST be able to fail against a fault-injecting mock target.

---

## 9. Relationship to existing work

DCTP sits **above** wire formats and adapters and **beside** benchmarks. It aims to be contributable, not competing.

| Work | What it does | How DCTP relates |
|---|---|---|
| **Decision Model Protocol, draft 0.1** (decisionmodelprotocol.io/specification/0.1) | Request/response rules and JSON Schemas for the `systemone`-style exchange; lists shared confidence, version negotiation, capability discovery, a common error envelope, and a conformance suite as open. | DCTP adopts DMP's response rules as its conformance check. Its capability descriptor (§4), registered confidence definitions (§5.4), and error envelope (§5.7) are offered to DMP as proposals for those open items. If DMP adopts equivalents, DCTP MUST defer to them. |
| **jevcompat** (mandu05.com) | Unofficial 48-requirement spec and test tool for `POST /v1/systemone` servers; proxy that repairs or refuses. | DCTP reuses its robustness rule and noise-aware testing method; jevcompat results MAY populate `method: probe` descriptor fields. |
| **sys1bench** (PyPI 0.3.2) | Calibration benchmarks for decision models. | General leaderboards; DCTP's `plan` is per-contract, on the user's own labeled data. `plan` MAY reuse sys1bench metric code. |
| **Buf `protoc-gen-jev`** (experimental) | Typed code generation from Protobuf for Jev. | Prior art for M5 codegen; a contract-to-proto bridge is an open question. |
| **Vercel AI SDK `experimental_decide`, AI Gateway `/v1/evaluate`, LiteLLM, OpenRouter, Pydantic AI `DecisionModel`** | Provider adapters and cross-provider calls; native values preserved; no cross-provider calibration promise; limited failover. | Compile targets (§5.6). DCTP supplies the contract, lockfile, fitted thresholds, and evidence-gated switching they do not. |
| **TypeSafe Jev** and Jev Harness | Jev defines the `systemone` shape; Jev Harness is an independent demo that compiles typed choice/score/noul questions into Jev requests and keeps the threshold in application code. | Jev Harness is the reference implementation; its threshold-outside-the-model design becomes DCTP's policy layer. DCTP is not affiliated with TypeSafe. |

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

## 11. Non-goals

- **Not a new wire protocol.** DCTP does not ask providers to change their APIs.
- **Not a model, router, or hosted gateway.** No inference, no traffic brokering, no billing.
- **Not a leaderboard.** `plan` results are per contract and per dataset, not general rankings.
- **No cross-model calibration guarantee.** Portable confidence standardizes the formula, not the meaning; per-model fitting remains required.
- **No certification of vendors.** Conformance levels apply to DCTP tooling. Provider conformance is reported, not certified.
- **No generative structured output.** Schema-constrained text generation (e.g. Claude or Gemini structured outputs) is out of scope for v0.1, though it MAY be added as a target type later for baseline comparison.

## 12. Open questions

1. **Camp convergence.** If DMP or a vendor consortium unifies the two camps, does DCTP's compiler collapse to one target family? (Desired outcome: yes, and the contract/lock/plan layers remain.)
2. **Portable confidence semantics.** Should DCTP define a *calibrated* portable confidence (e.g. per-model isotonic mapping stored in the lockfile), or only formulas?
3. **Split requests vs. shared context.** When a contract exceeds a target's question limit, is splitting acceptable by default, or should `atomic: true` be the default?
4. **Contract-to-proto bridge.** Should contracts compile to Protobuf to reuse `protoc-gen-jev`, or stay JSON Schema-only?
5. **Eval data privacy.** How should `plan` run against hosted providers when eval data is sensitive (e.g. banks)? Options: residency-aware target filtering, local-only `plan` with open-weight models.
6. **Descriptor governance.** Who can merge vendor-submitted descriptor changes, and how are disputes between docs and probes resolved?
7. **Polyfill boundaries.** Which fallbacks are safe to apply automatically, and which should always require an explicit contract opt-in?
8. **Experimental types.** Should `box` and `extract` be in v0.2, given immature and inconsistent provider support?
9. **Version negotiation.** How should the runtime react when a provider silently updates a pinned model? (Detection via response fingerprinting vs. trusting version headers.)

---

## 13. Open decisions reserved for David (added in 0.1.1)

These are marked OPEN-DECISION where they arise. Nothing in 0.1.1 decides them.

1. Camp definition rule: body vocabulary vs path vs an added gateway camp (§2).
2. Box/experimental fallback rule: §5.3 vs §5.9 (§5.3).
3. Grammars: `policy` block keys, `confidence` block, `accept` expressions (including "incumbent" and MUST markers), `targets_query`, and `eval.paraphrases` (used in examples, unspecified).
4. Canonical target-id format (§5.7).
5. Hash canonicalization for `content_hash` and `request_hash` (e.g. RFC 8785 JCS plus a YAML 1.2 normalization rule).
6. Naming: the project name (TBD), the capability path scheme (`features.` prefix or not), the score-spread confidence names, and "System 1" vs "System One".
7. M2 lock-before-plan vs principle 5 (§10).
8. Bare `applies_to: portable` in examples vs §5.4's named-definition rule, and the threshold direction when a yes/no rule fires on "no".

---

*Vendor facts in this draft reflect research on 2026-10-25 and are non-normative. They belong in descriptors, not in the spec, and will change.*
