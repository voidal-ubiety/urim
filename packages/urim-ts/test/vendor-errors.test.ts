// Per-vendor error maps (from public vendor docs, checked 2026-10-28 EDT).
import { test } from "node:test";
import assert from "node:assert/strict";
import { decodeReply, tier, classifyVendorReply, DESCRIPTORS, defineDecision } from "../src/index.ts";
import { triage, severity, JEV, OPENAI, inputSchema } from "./fixtures.ts";

const fail = (status: number, body: unknown = {}, headers: Record<string, string> = {}) => ({ status, headers, body, latencyMs: 1 });
const oaiErr = (code: string) => ({ error: { message: "m", type: "t", code } }); // https://developers.openai.com/api/docs/guides/error-codes.md
const FASTINO = tier({ provider: "fastino", model: "GLiDE", version: "1", camp: "systemone", questionTypes: ["noul", "choice"] });
const PPLX = tier({ provider: "perplexity", model: "pplx-decider-latest", version: "v1.2", camp: "systemone", questionTypes: ["noul", "choice"] });

const cases: Array<[string, keyof typeof DESCRIPTORS, number, unknown, string]> = [
  ["openai 429 credit_balance_exhausted", "openai", 429, oaiErr("credit_balance_exhausted"), "quota_exceeded"],
  ["openai 429 organization_spend_limit_exceeded", "openai", 429, oaiErr("organization_spend_limit_exceeded"), "quota_exceeded"],
  ["openai 429 project_spend_limit_exceeded", "openai", 429, oaiErr("project_spend_limit_exceeded"), "quota_exceeded"],
  ["openai 429 organization_usage_limit_exceeded", "openai", 429, oaiErr("organization_usage_limit_exceeded"), "quota_exceeded"],
  ["openai 429 rate_limit_exceeded", "openai", 429, oaiErr("rate_limit_exceeded"), "rate_limited"],
  ["openai 429 no body", "openai", 429, {}, "rate_limited"],
  ["openai 503 server_is_overloaded", "openai", 503, oaiErr("server_is_overloaded"), "provider_unavailable"],
  ["openai 503 service_unavailable_error", "openai", 503, oaiErr("service_unavailable_error"), "provider_unavailable"],
  ["typesafe 529", "typesafe", 529, {}, "provider_unavailable"],
  ["typesafe 429", "typesafe", 429, {}, "rate_limited"],
  ["fastino 402", "fastino", 402, {}, "quota_exceeded"],
  ["fastino 425", "fastino", 425, {}, "provider_unavailable"],
  ["perplexity 429 (code ignored)", "perplexity", 429, oaiErr("credit_balance_exhausted"), "rate_limited"],
  ["perplexity 413", "perplexity", 413, {}, "invalid_request"],
  ["liquid 402 (generic)", "liquid", 402, {}, "invalid_request"],
];
for (const [name, provider, status, body, expected] of cases) {
  test(`vendor map: ${name} -> ${expected}`, () =>
    assert.equal(classifyVendorReply(DESCRIPTORS[provider]!, fail(status, body)).type, expected));
}
test("2xx is not an error", () => assert.equal(classifyVendorReply(DESCRIPTORS["openai"]!, fail(200)).type, null));

test("fastino 425 exposes retryAfterMs from Retry-After seconds", () => {
  const r = decodeReply(triage, FASTINO, fail(425, {}, { "Retry-After": "3", "x-should-retry": "true" }));
  assert.ok(!r.ok); assert.equal(r.error.type, "provider_unavailable"); assert.equal(r.error.retryAfterMs, 3000);
});
test("openai errors carry x-request-id", () => {
  const r = decodeReply(severity, OPENAI, fail(429, oaiErr("credit_balance_exhausted"), { "x-request-id": "req_abc" }));
  assert.ok(!r.ok); assert.equal(r.error.type, "quota_exceeded"); assert.equal(r.error.requestId, "req_abc");
});
test("a systemone descriptor with no request-id header reads none", () => {
  const r = decodeReply(triage, JEV, fail(529, {}, { "x-request-id": "ignored" }));
  assert.ok(!r.ok); assert.equal(r.error.requestId, undefined);
});
test("perplexity request id read when present", () => {
  const r = decodeReply(triage, PPLX, fail(500, {}, { "x-request-id": "u-1" }));
  assert.ok(!r.ok); assert.equal(r.error.requestId, "u-1");
});
test("a tier whose camp contradicts its descriptor is an invalid definition", () => {
  const wrong = tier({ provider: "perplexity", model: "pplx-decider-latest", version: "v1.2", camp: "decisions", questionTypes: ["noul"] });
  assert.throws(() => defineDecision({ contract: "x@1.0.0", tiers: [wrong], input: inputSchema,
    questions: {}, failover: { on: [] }, thresholds: {} }), { type: "invalid_definition" });
});
