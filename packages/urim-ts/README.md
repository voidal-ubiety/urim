# urim

A typed client for system-1 decision APIs: define a decision once, call it across providers,
and get every answer back with its confidence, the tier that served it and a stable envelope.

**Status:** pre-alpha (0.0.1). The API may change. Node.js 23.6 or later.

```sh
npm install urim
```

## Quickstart (offline)

This runs without a network or API key: `fakeProvider` from `urim` scripts the provider's reply.

```js
import { createClient, defineDecision, tier, noul, fakeProvider } from "urim";

// OpenAI publishes no model version, so "0.0.0" is a placeholder.
const openai = tier({ provider: "openai", model: "gpt-6-luna", version: "0.0.0", camp: "decisions", questionTypes: ["noul"] });

const triage = defineDecision({
  contract: "incident-triage@1.0.0",
  tiers: [openai],
  // Any { parse, toJSONSchema } works; `zodSchema` from "urim/zod" adapts a Zod schema.
  input: { parse: (value) => ({ ok: true, value }), toJSONSchema: () => ({ type: "object" }) },
  questions: { page: noul("Should someone be paged right now?", { yes: "Active customer impact", no: "No impact" }) },
  failover: { on: ["timeout", "provider_unavailable"] },
  thresholds: {},
});

// Offline: a scripted provider stands in for the network. For real calls use `openaiDecisions()` from "urim/adapters".
const provider = fakeProvider({
  [openai.id]: [{ body: { model: "gpt-6-luna", answers: [{ type: "predicate", name: "page", probability: 0.95 }] } }],
});
const result = await createClient({ adapters: [provider] }).decide(triage, { report: "checkout API returns 500s" });
console.log(result.ok ? result.value.page : result.error.type);
```

It prints the answer: `value: 'yes'`, `confidence: 0.9` and where the confidence came from.

Entry points: `urim` (core), `urim/adapters` (network adapters, opt-in), `urim/zod` (Zod v4 input schemas,
optional peer) and `urim/testing`. The `urim` CLI (`npx urim --help`) emits contract files.

## Camps
The wire format is chosen by request **body**, not URL path (`src/descriptors.ts`):

| Provider | Body camp | URL | Auth env |
|---|---|---|---|
| OpenAI | decisions | `https://api.openai.com/v1/decisions` | `OPENAI_API_KEY` (Bearer) |
| Perplexity | systemone | `https://api.perplexity.ai/v1/decisions` | `PERPLEXITY_API_KEY` |
| Inception | systemone | `https://api.inceptionlabs.ai/v1/decisions` | `INCEPTION_API_KEY` |
| Microsoft | systemone | `{endpoint}/providers/microsoft/v1/systemone` | `AZURE_API_KEY` (`api-key`) or Entra Bearer |
| Cloudflare | systemone | `…/accounts/{account_id}/ai/run/@cf/cloudflare/{model}` | `CLOUDFLARE_AUTH_TOKEN` |
| Liquid | systemone | `https://api.liquid.ai/decisions/v1/systemone` | `LIQUID_API_KEY` |
| Fastino | systemone | `https://api.fastino.ai/v1/systemone` | `FASTINO_API_KEY` (`X-API-Key`) |

## Real adapters (opt-in)
Two adapters ship, one per request format (`systemone` and `decisions`), and only via the subpath import:

```ts
import { createClient } from "urim";
import { openaiDecisions } from "urim/adapters";
const client = createClient({ adapters: [openaiDecisions()], env: process.env });
```

The credential is read from the named env var at send time and never logged. A missing key fails as `auth`
before any request. Tests use a mocked `fetch`; no live call has been made from this package.

## Confidence
- systemone noul and decisions predicate: the normalized formula `(p_max − 1/n)/(1 − 1/n)`, n = 2, computed client-side.
- choice/score: the vendor's own `confidence`, passed through. OpenAI's formula is undocumented.
- Every answer says which: `confidenceSource: "native" | "urim_derived" | null`.

## Cost
Estimated only: input tokens × a dated price per 1M (output free). See `test/fixtures/prices.vendor-2026-10-28.json`.
Before a call, the budget skip estimates input tokens as the UTF-8 byte length of the encoded JSON body
(unverified, conservative heuristic) and reports `costSource: "estimated_pre_call"` in `explain()`.

## Development

```sh
npm run typecheck   # tsc, strict
npm test            # node:test, no network
```

Vendor facts come from public vendor docs, checked 2026-10-28 EDT.
