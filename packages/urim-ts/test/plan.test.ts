import { test } from "node:test";
import assert from "node:assert/strict";
import { explain, nextStep } from "../src/index.ts";
import { triage, prices, JEV, CLEF } from "./fixtures.ts";

test("plan calls tiers in declared order", () =>
  assert.deepEqual(explain(triage).steps.map((s) => [s.tier.id, s.action]), [[JEV.id, "call"], [CLEF.id, "call"]]));
test("no budget means nothing is skipped", () =>
  assert.ok(explain(triage, { prices }).steps.every((s) => s.action === "call")));
test("tier estimated over budget is skipped with reason budget", () => {
  const plan = explain(triage, { prices, budget: { maxCost: 0.002, currency: "USD" } });
  assert.deepEqual(plan.steps[0], { tier: JEV, action: "skip", reason: "budget", estimatedCost: 0.004, costSource: "per_call" });
  assert.equal(plan.steps[1]?.action, "call");
});
test("unknown cost is never skipped", () => {
  const plan = explain(triage, { prices: { ...prices, entries: {} }, budget: { maxCost: 0, currency: "USD" } });
  assert.ok(plan.steps.every((s) => s.action === "call" && s.estimatedCost === null));
});
test("currency mismatch counts as unknown cost, not skipped", () =>
  assert.equal(explain(triage, { prices, budget: { maxCost: 0, currency: "EUR" } }).steps[0]?.action, "call"));
test("budget skip only applies when budget is in failover.on", () => {
  const noBudget = { ...triage, failover: { on: ["timeout"] as const } };
  assert.equal(explain(noBudget, { prices, budget: { maxCost: 0, currency: "USD" } }).steps[0]?.action, "call");
});
test("plan is frozen data", () => assert.ok(Object.isFrozen(explain(triage).steps)));

test("listed failover type moves to next tier", () => assert.equal(nextStep(triage, "timeout"), "next"));
test("unlisted type abstains", () => assert.equal(nextStep(triage, "nonconformant_response"), "abstain"));
for (const t of ["cancelled", "auth", "invalid_input", "invalid_request"] as const) {
  test(`${t} never fails over`, () => assert.equal(nextStep(triage, t), "abstain"));
}
