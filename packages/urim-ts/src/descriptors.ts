// D: provider descriptors. Pure data, one row per vendor, every value taken from
// public vendor docs (checked 2026-10-28 EDT). The camp is chosen by BODY vocabulary,
// never by URL path: Perplexity and Inception post the systemone body to a `/v1/decisions` path.
// Anything the research marks UNKNOWN is null here and tagged TODO(vendor-fact); null means "use the
// conservative generic behaviour", never a guess.
import type { ErrorType } from "./errors.ts";
import type { Camp, Tier } from "./types.ts";

/** How the credential travels. `env` is the NAME of the variable; the value is read at send time only. */
export type AuthSpec = { readonly header: string; readonly scheme: "Bearer" | null; readonly env: string };

/** wire = the `model` string we send; answeredAs = response `model` values that still mean this tier. */
export type ModelSpec = { readonly wire: string; readonly answeredAs: readonly string[] };

/** 429/503 bodies that carry `error.code`; matched before the status map. */
export type CodeRule = { readonly status: number; readonly codes: Readonly<Record<string, ErrorType>> };

export type ErrorMap = {
  readonly byStatus: Readonly<Record<number, ErrorType>>;
  readonly byCode: readonly CodeRule[];
  /** Headers that, when present, make a non-2xx reply retryable later (exposed as retryAfterMs). */
  readonly retryHeaders: readonly string[];
};

export type Descriptor = {
  readonly provider: string;
  readonly camp: Camp;
  /** URL template. `{endpoint}`, `{account_id}`, `{model}` are filled by the adapter from options/tier. */
  readonly url: string;
  readonly auth: readonly AuthSpec[];
  /** "registry": tier.model maps through `models`. "deployment": wire model is the caller's deployment name (Microsoft). */
  readonly modelNaming: "registry" | "deployment";
  readonly models: Readonly<Record<string, ModelSpec>>;
  /** Response header carrying the served model, when the vendor documents one (Fastino). */
  readonly servedModelHeader: string | null;
  readonly requestIdHeader: string | null;
  readonly errors: ErrorMap;
  readonly sources: readonly string[];
  /** Set only for a provider documented to send `confidence: 0` with empty `probabilities` as an "unavailable"
   *  sentinel (e.g. a gateway); such answers then decode as confidence null. No shipped descriptor sets it. */
  readonly confidenceUnavailableSentinel?: true;
};

/** Generic map for undocumented vendors (unchanged from slice 1). */
export const GENERIC_ERRORS: ErrorMap = {
  byStatus: { 401: "auth", 403: "auth", 408: "timeout", 429: "rate_limited", 504: "timeout" },
  byCode: [], retryHeaders: ["retry-after"],
};

const bearer = (env: string): AuthSpec => ({ header: "authorization", scheme: "Bearer", env });

export const DESCRIPTORS: Readonly<Record<string, Descriptor>> = {
  typesafe: {
    provider: "typesafe", camp: "systemone", url: "https://api.typesafe.ai/v1/systemone",
    auth: [bearer("TYPESAFE_API_KEY")], modelNaming: "registry",
    // S2: jev-latest and jev-preview both resolve to jev-1.14.0 (as of 2026-10-28).
    models: {
      "jev@1.14.0": { wire: "jev-1.14.0", answeredAs: ["jev-1.14.0"] },
      "jev@1.13.0": { wire: "jev-1.13.0", answeredAs: ["jev-1.13.0"] },
      "jev-latest": { wire: "jev-latest", answeredAs: ["jev-1.14.0"] },
      "jev-preview": { wire: "jev-preview", answeredAs: ["jev-1.14.0"] },
    },
    servedModelHeader: null,
    requestIdHeader: null, // TODO(vendor-fact): header name unknown; SDK exposes result.request_id (S6)
    // S3: 529 Overloaded. 400 max_tokens_exceeded body shape unknown -> stays invalid_request.
    errors: { ...GENERIC_ERRORS, byStatus: { ...GENERIC_ERRORS.byStatus, 529: "provider_unavailable" } },
    sources: ["https://docs.typesafe.ai/api/system-one", "https://docs.typesafe.ai/models", "https://docs.typesafe.ai/api/errors.md"],
  },
  openai: {
    provider: "openai", camp: "decisions", url: "https://api.openai.com/v1/decisions",
    auth: [bearer("OPENAI_API_KEY")], modelNaming: "registry",
    models: { "gpt-6-luna": { wire: "gpt-6-luna", answeredAs: ["gpt-6-luna"] } }, // O1: only gpt-6-luna; versioned response ids TODO(vendor-fact)
    servedModelHeader: null, requestIdHeader: "x-request-id", // O5
    errors: { // O4: distinguish quota from rate limit via error.code
      byStatus: { ...GENERIC_ERRORS.byStatus, 503: "provider_unavailable" },
      byCode: [{ status: 429, codes: {
        credit_balance_exhausted: "quota_exceeded", organization_spend_limit_exceeded: "quota_exceeded",
        project_spend_limit_exceeded: "quota_exceeded", organization_usage_limit_exceeded: "quota_exceeded" } }],
      retryHeaders: ["retry-after"],
    },
    sources: ["https://developers.openai.com/api/reference/typescript/resources/decisions/methods/create/index.md",
      "https://developers.openai.com/api/docs/guides/error-codes.md", "https://developers.openai.com/api/reference/overview.md"],
  },
  microsoft: {
    provider: "microsoft", camp: "systemone", url: "{endpoint}/providers/microsoft/v1/systemone",
    auth: [{ header: "api-key", scheme: null, env: "AZURE_API_KEY" }, bearer("AZURE_ENTRA_TOKEN")], // M1; Entra env name is OUR choice
    modelNaming: "deployment", models: {}, servedModelHeader: null,
    requestIdHeader: null, // TODO(vendor-fact)
    errors: GENERIC_ERRORS, // M1 lists 400/401/403/404/422/429; generic map covers them. Quota vs rate: TODO(vendor-fact)
    sources: ["https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision"],
  },
  cloudflare: {
    provider: "cloudflare", camp: "systemone",
    url: "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/{model}",
    auth: [bearer("CLOUDFLARE_AUTH_TOKEN")], modelNaming: "registry",
    models: { clef: { wire: "clef", answeredAs: ["clef"] }, "clef-flash": { wire: "clef-flash", answeredAs: ["clef-flash"] } },
    servedModelHeader: null, requestIdHeader: null, // TODO(vendor-fact): REST envelope, errors, request id
    errors: GENERIC_ERRORS, sources: ["https://developers.cloudflare.com/workers-ai/models/clef/"],
  },
  liquid: {
    provider: "liquid", camp: "systemone", url: "https://api.liquid.ai/decisions/v1/systemone",
    auth: [bearer("LIQUID_API_KEY")], modelNaming: "registry",
    models: {}, servedModelHeader: null, requestIdHeader: null, errors: GENERIC_ERRORS, // TODO(vendor-fact)
    sources: ["https://docs.liquid.ai/lfm/models/d1"],
  },
  perplexity: {
    provider: "perplexity", camp: "systemone", url: "https://api.perplexity.ai/v1/decisions", // systemone BODY
    auth: [bearer("PERPLEXITY_API_KEY")], modelNaming: "registry",
    models: {
      "pplx-decider-latest": { wire: "pplx-decider-latest", answeredAs: ["pplx-decider-v1.2"] },
      "pplx-decider-flash-latest": { wire: "pplx-decider-flash-latest", answeredAs: ["pplx-decider-flash-v1.2"] },
    },
    servedModelHeader: null, requestIdHeader: "x-request-id", // P1 (absent on 401/404)
    errors: GENERIC_ERRORS, // P1: branch on HTTP status, not code; quota vs rate TODO(vendor-fact)
    sources: ["https://docs.perplexity.ai/api-reference/decisions-post"],
  },
  fastino: {
    provider: "fastino", camp: "systemone", url: "https://api.fastino.ai/v1/systemone",
    auth: [{ header: "x-api-key", scheme: null, env: "FASTINO_API_KEY" }, bearer("FASTINO_API_KEY")], modelNaming: "registry",
    models: { GLiDE: { wire: "fastino/GLiDE", answeredAs: ["glide", "fastino/GLiDE"] } }, // F2
    servedModelHeader: "x-fastino-served-model", requestIdHeader: null, // TODO(vendor-fact): request id
    errors: { byStatus: { ...GENERIC_ERRORS.byStatus, 402: "quota_exceeded", 425: "provider_unavailable" },
      byCode: [], retryHeaders: ["retry-after", "x-should-retry"] }, // F1
    sources: ["https://docs.fastino.ai/openapi.json", "https://docs.fastino.ai/inference/systemone.md"],
  },
  inception: {
    provider: "inception", camp: "systemone", url: "https://api.inceptionlabs.ai/v1/decisions", // systemone BODY
    auth: [bearer("INCEPTION_API_KEY")], modelNaming: "registry",
    models: {}, servedModelHeader: null, requestIdHeader: null, errors: GENERIC_ERRORS, // TODO(vendor-fact)
    sources: ["https://docs.inceptionlabs.ai/capabilities/decisions.md"],
  },
};

/** Fallback descriptor for providers we have no facts for: generic errors, wire model = tier model. */
const genericFor = (tier: Tier): Descriptor => ({
  provider: tier.provider, camp: tier.camp, url: "", auth: [], modelNaming: "registry", models: {},
  servedModelHeader: null, requestIdHeader: null, errors: GENERIC_ERRORS, sources: [],
});

export const descriptorFor = (tier: Tier): Descriptor => DESCRIPTORS[tier.provider] ?? genericFor(tier);

export const modelSpecFor = (d: Descriptor, tier: Tier): ModelSpec =>
  d.models[`${tier.model}@${tier.version}`] ?? d.models[tier.model] ?? { wire: tier.model, answeredAs: [tier.model] };

/** Lowercase-insensitive header read. */
export const header = (headers: Readonly<Record<string, string>>, name: string): string | undefined => {
  const key = Object.keys(headers).find((k) => k.toLowerCase() === name);
  return key === undefined ? undefined : headers[key];
};
