// Test fixtures. Tier model ids follow public vendor docs (checked 2026-10-28 EDT); prices here are PLACEHOLDERS.
import { tier, defineDecision, noul, choice, score, threshold } from "../src/index.ts";
import type { PriceTable, SchemaAdapter } from "../src/index.ts";

export const JEV = tier({ provider: "typesafe", model: "jev", version: "1.14.0", camp: "systemone",
  questionTypes: ["noul", "choice", "score"] });                       // PLACEHOLDER version
export const CLEF = tier({ provider: "cloudflare", model: "clef-flash", version: "x.y.z", camp: "systemone",
  questionTypes: ["noul", "choice"] });                                // TODO(vendor-fact): camp, version, types
export const OPENAI = tier({ provider: "openai", model: "gpt-6-luna", version: "0.0.0", camp: "decisions",
  questionTypes: ["noul", "choice", "score"] }); // model per O1; OpenAI publishes no version -> 0.0.0 PLACEHOLDER

type Input = { report: string };
// Minimal schema stand-in for the internal SchemaAdapter (Zod adapter is a later slice).
export const inputSchema: SchemaAdapter<Input> = {
  parse: (value) => {
    const ok = typeof value === "object" && value !== null && typeof (value as Input).report === "string";
    return ok ? { ok: true, value: value as Input } : { ok: false, issues: [{ path: "report", message: "expected string" }] };
  },
  toJSONSchema: () => ({ type: "object", required: ["report"], properties: { report: { type: "string" } } }),
};

export const triage = defineDecision({
  contract: "incident-triage@2.0.0",
  tiers: [JEV, CLEF],
  input: inputSchema,
  questions: {
    page: noul("Should someone be paged right now?", { yes: "Active impact", no: "No impact" }),
    team: choice("Which team owns this incident?", { billing: "b", platform: "p", identity: "i", data: "d" }),
  },
 
  failover: { on: ["timeout", "provider_unavailable", "rate_limited", "budget"] },
  thresholds: {
    page_oncall: threshold({ on: "page", default: 0.8, objective: { minPrecision: 0.95 } }), // 0.8 PLACEHOLDER
    auto_route: threshold({ on: "team", objective: { escalationRate: 0.15 } }),
  },
});

export const severity = defineDecision({
  contract: "severity@1.0.0",
  tiers: [OPENAI, JEV],
  input: inputSchema,
  questions: { sev: score("How severe?", { low: "l", mid: "m", high: "h" }), page: noul("Page?", { yes: "y", no: "n" }) },
 
  failover: { on: ["timeout"] },
  thresholds: {},
});

export const prices: PriceTable = {
  id: "fixture-prices", asOf: "2026-10-28", url: "https://example.invalid/PLACEHOLDER",
  entries: { [JEV.id]: { perCall: 0.004, currency: "USD" }, [CLEF.id]: { perCall: 0.001, currency: "USD" } },
}; // PLACEHOLDER numbers
