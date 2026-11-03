// Cost = input tokens x dated price; output free; always "estimated".
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildEnvelope, emit } from "../src/index.ts";
import type { PriceTable } from "../src/index.ts";
import { triage, JEV } from "./fixtures.ts";

const vendorPrices = JSON.parse(readFileSync(new URL("./fixtures/prices.vendor-2026-10-28.json", import.meta.url), "utf8")) as PriceTable & { entries: Record<string, { source: string | null; perMInputTokens: number | null }> };
const parts = { def: triage, contractHash: emit(triage).hash, tier: JEV, answers: {}, cuts: {}, attempts: [], requestIds: {}, at: "t" };

test("every vendor price entry carries a source URL and an as-of date", () => {
  for (const [id, e] of Object.entries(vendorPrices.entries)) {
    assert.ok(e.perMInputTokens === null || typeof e.source === "string", `${id} has a price but no source`);
  }
  assert.equal(vendorPrices.asOf, "2026-10-28");
});
test("JEV: 1,000,000 input tokens at $0.042 -> $0.042 estimated, output free", () => {
  const env = buildEnvelope({ ...parts, prices: vendorPrices, providerUsage: { inputTokens: 1_000_000, outputTokens: 50, cost: null } });
  assert.ok(Math.abs((env.usage.cost?.amount ?? 0) - 0.042) < 1e-12);
  assert.equal(env.usage.cost?.source, "estimated");
  assert.equal(env.usage.cost?.priceTable?.asOf, "2026-10-28");
});
test("token price with unknown token count -> cost null (never invented)", () => {
  const env = buildEnvelope({ ...parts, prices: vendorPrices, providerUsage: { inputTokens: null, outputTokens: null, cost: null } });
  assert.equal(env.usage.cost, null);
});
test("null price (Microsoft, Liquid) -> cost null", () => {
  assert.equal(vendorPrices.entries["microsoft/*"]?.perMInputTokens, null);
  assert.equal(vendorPrices.entries["liquid/*"]?.perMInputTokens, null);
});
