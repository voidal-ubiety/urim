import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emit, defineDecision, score } from "../src/index.ts";
import { triage, JEV, inputSchema } from "./fixtures.ts";

const golden = JSON.parse(readFileSync(new URL("./golden/triage.emit.json", import.meta.url), "utf8")) as { json: string; hash: string };

test("emit of triage matches golden canonical JSON", () => assert.equal(emit(triage).json, golden.json));
test("emit of triage matches golden hash", () => assert.equal(emit(triage).hash, golden.hash));
test("emit is deterministic", () => assert.deepEqual(emit(triage), emit(triage)));
test("emitted document carries contract id, tiers and input JSON Schema", () => {
  const doc = emit(triage).document as Record<string, unknown>;
  assert.equal(doc["contract"], "incident-triage@2.0.0");
  assert.deepEqual((doc["tiers"] as Array<{ id: string }>).map((t) => t.id), [JEV.id, "cloudflare/clef-flash@x.y.z"]);
  assert.deepEqual(doc["input"], inputSchema.toJSONSchema());
});
test("score level order is part of the contract (options emitted as an ordered list)", () => {
  const mk = (levels: Record<string, string>) => defineDecision({ contract: "s@1.0.0", tiers: [JEV], input: inputSchema,
    questions: { s: score("q", levels) }, failover: { on: [] }, thresholds: {} });
  assert.notEqual(emit(mk({ low: "l", high: "h" })).hash, emit(mk({ high: "h", low: "l" })).hash);
});
test("hooks change the hash only by presence, not by code", () => {
  const a = defineDecision({ ...triage, interpret: () => 1 });
  const b = defineDecision({ ...triage, interpret: () => 2 });
  assert.equal(emit(a).hash, emit(b).hash);
  assert.notEqual(emit(a).hash, emit(triage).hash);
});
