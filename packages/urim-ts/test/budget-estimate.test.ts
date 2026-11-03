// Slice 4b fix 1: pre-call cost estimate for the budget skip, from the encoded request size x a dated token price.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createClient, encodeRequest, explain, fakeProvider } from "../src/index.ts";
import { estimateInputTokens } from "../src/plan.ts";
import type { PriceTable } from "../src/index.ts";
import { triage, JEV, CLEF } from "./fixtures.ts";
import { triageOk } from "./wire.ts";

const input = { report: "db primary unreachable since 02:00" };
const tokenPrices = (perM: number): PriceTable => ({ id: "t", asOf: "2026-10-28", url: "u",
  entries: { [JEV.id]: { perMInputTokens: perM, perMOutputTokens: 0, currency: "USD", source: "s" } } });
const bytes = new TextEncoder().encode(JSON.stringify(encodeRequest(triage, JEV, input).body)).length;

test("token estimate = UTF-8 bytes of the encoded JSON body (pure, deterministic)", () => {
  const req = encodeRequest(triage, JEV, input);
  assert.equal(estimateInputTokens(req), bytes);
  assert.equal(estimateInputTokens(req), estimateInputTokens(req));
  assert.equal(estimateInputTokens({ ...req, body: { s: "é" } }), new TextEncoder().encode('{"s":"é"}').length);
});
test("over budget: token-priced tier is skipped, estimate and source shown", () => {
  const perM = 1_000_000; // $1 per token -> estimate = bytes dollars
  const step = explain(triage, { prices: tokenPrices(perM), budget: { maxCost: bytes - 1, currency: "USD" }, input }).steps[0];
  assert.equal(step?.action, "skip");
  assert.equal(step?.estimatedCost, bytes);
  assert.equal(step?.costSource, "estimated_pre_call");
  assert.equal(step?.estimatedInputTokens, bytes);
});
test("under budget: token-priced tier is called", () => {
  const step = explain(triage, { prices: tokenPrices(1_000_000), budget: { maxCost: bytes, currency: "USD" }, input }).steps[0];
  assert.equal(step?.action, "call");
  assert.equal(step?.costSource, "estimated_pre_call");
});
test("missing price row is never skipped (D5)", () => {
  const step = explain(triage, { prices: tokenPrices(1), budget: { maxCost: 0, currency: "USD" }, input }).steps[1];
  assert.equal(step?.tier.id, CLEF.id);
  assert.deepEqual([step?.action, step?.estimatedCost, step?.costSource], ["call", null, null]);
});
test("null token price is never skipped (D5)", () => {
  const p: PriceTable = { ...tokenPrices(1), entries: { [JEV.id]: { perMInputTokens: null, currency: "USD" } } };
  const step = explain(triage, { prices: p, budget: { maxCost: 0, currency: "USD" }, input }).steps[0];
  assert.deepEqual([step?.action, step?.costSource], ["call", null]);
});
test("token-priced row without input: unknown, never skipped", () => {
  const step = explain(triage, { prices: tokenPrices(1_000_000), budget: { maxCost: 0, currency: "USD" } }).steps[0];
  assert.deepEqual([step?.action, step?.estimatedCost, step?.costSource], ["call", null, null]);
});
test("flat perCall row reports source per_call", () => {
  const p: PriceTable = { ...tokenPrices(1), entries: { [JEV.id]: { perCall: 0.004, currency: "USD" } } };
  assert.equal(explain(triage, { prices: p, input }).steps[0]?.costSource, "per_call");
});
test("client.explain(def, {input}) shows the pre-call estimate", () => {
  const c = createClient({ adapters: [fakeProvider({})], prices: tokenPrices(1_000_000), budget: { maxCost: 1, currency: "USD" } });
  const step = c.explain(triage, { input }).steps[0];
  assert.deepEqual([step?.action, step?.costSource], ["skip", "estimated_pre_call"]);
});
test("decide skips on the pre-call estimate and calls the next tier; estimate never re-applied after the reply", async () => {
  const fake = fakeProvider({ [CLEF.id]: [{ body: triageOk() }] });
  const prices: PriceTable = { ...tokenPrices(1_000_000), entries: {
    ...tokenPrices(1_000_000).entries, [CLEF.id]: { perMInputTokens: 0.000001, perMOutputTokens: 0, currency: "USD" } } };
  const c = createClient({ adapters: [fake], prices, budget: { maxCost: 1, currency: "USD" } });
  const r = await c.decide(triage, input);
  assert.equal(r.ok, true);
  assert.deepEqual(r.ok ? r.envelope.attempts.map((a) => [a.tier, a.outcome]) : [], [[JEV.id, "skipped_budget"], [CLEF.id, "ok"]]);
  assert.equal(fake.calls.length, 1);
});
