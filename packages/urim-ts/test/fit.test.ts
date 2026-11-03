import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runFit, parseCases, estimateFitCost } from "../src/fit.ts";
import { fakeProvider } from "../src/index.ts";
import type { FakeStep } from "../src/index.ts";
import { gate } from "./fixtures/fit.decision.ts";
import { JEV, CLEF, prices } from "./fixtures.ts";

const cases = parseCases(readFileSync(new URL("./fixtures/eval.fit.jsonl", import.meta.url), "utf8"));
const script = JSON.parse(readFileSync(new URL("./fixtures/fake.fit.json", import.meta.url), "utf8")) as Record<string, FakeStep[]>;
const fake = () => fakeProvider(script, { cycle: true });
const fixedNow = () => Date.parse("2026-10-28T21:00:00.000Z");

test("cost estimate = cases x repeat x per-call price, per tier", () =>
  assert.deepEqual(estimateFitCost(gate, 5, 2, prices), { perTier: { [JEV.id]: 0.04, [CLEF.id]: 0.01 }, total: 0.05, currency: "USD", unknown: [] }));
test("unknown price is listed, never guessed", () => {
  const e = estimateFitCost(gate, 5, 1, { ...prices, entries: {} });
  assert.deepEqual([e.total, e.unknown], [null, [JEV.id, CLEF.id]]);
});
test("without yes: refuses, makes no calls, returns the estimate", async () => {
  const f = fake();
  const r = await runFit({ def: gate, cases, adapters: [f], prices, repeat: 1, yes: false });
  assert.equal(r.status, "needs_confirmation");
  assert.equal(f.calls.length, 0);
});
test("fits cutoffs per tier (hand-checked) and writes a lock", async () => {
  const r = await runFit({ def: gate, cases, adapters: [fake()], prices, repeat: 1, yes: true, now: fixedNow });
  assert.equal(r.status, "ok");
  assert.ok(r.status === "ok");
  // JEV: (0.9T,0.8T,0.7F,0.6T,0.5F) minPrecision .75 -> 0.6. CLEF all correct -> lowest 0.75.
  assert.deepEqual(r.lock.cuts, { gate: { [JEV.id]: 0.6, [CLEF.id]: 0.75 } });
  assert.equal(r.lock.eval?.n, 5);
  assert.equal(r.lock.eval?.objectivesMet, true);
});
test("unmet objective: no lock, report says which", async () => {
  const strict = { ...gate, thresholds: { gate: { ...gate.thresholds.gate, objective: { minPrecision: 1.01 } } } };
  const r = await runFit({ def: strict, cases, adapters: [fake()], prices, repeat: 1, yes: true });
  assert.equal(r.status, "objectives_unmet");
  assert.ok(r.status === "objectives_unmet" && r.unmet.includes(`gate@${JEV.id}`));
});
test("repeat report: accuracy, flip rate, brier, latency, cost", async () => {
  const r = await runFit({ def: gate, cases, adapters: [fake()], prices, repeat: 2, yes: true, now: fixedNow });
  assert.ok(r.status === "ok");
  const jev = r.report.tiers[JEV.id]!;
  assert.equal(jev.questions["page"]?.accuracy, 0.6);
  assert.equal(jev.questions["page"]?.flipRate, 0);            // fake is deterministic per case
  assert.equal(jev.accuracyStdev, 0);
  assert.ok(Math.abs((jev.questions["page"]?.brier ?? -1) - 0.19) < 1e-12); // (.01+.04+.49+.16+.25)/5 = .95/5
  assert.equal(jev.cost?.amount, 0.04);
  assert.equal(typeof jev.latencyMs.p50, "number");
  assert.equal(r.lock.eval?.repeat, 2);
});
test("setHash changes when the eval set changes", async () => {
  const a = await runFit({ def: gate, cases, adapters: [fake()], prices, repeat: 1, yes: true });
  const b = await runFit({ def: gate, cases: cases.slice(1), adapters: [fake()], prices, repeat: 1, yes: true });
  assert.ok(a.status !== "needs_confirmation" && b.status !== "needs_confirmation");
  assert.notEqual(a.setHash, b.setHash);
});
test("parseCases rejects a line without labels", () => assert.throws(() => parseCases('{"input":{}}\n')));
