# urim (TypeScript)

Urim client v1 for system-1 decision APIs. Vendor facts come from
public vendor docs, checked 2026-10-28 EDT; nothing probed live.

```sh
npm run typecheck   # tsc, strict
npm test            # node:test, no network
```

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
