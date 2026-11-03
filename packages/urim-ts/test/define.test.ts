import { test } from "node:test";
import assert from "node:assert/strict";
import { defineDecision, noul, choice, threshold, tier, UrimError } from "../src/index.ts";
import { JEV, CLEF, triage, inputSchema } from "./fixtures.ts";

const base = { contract: "x@1.0.0", input: inputSchema,
  failover: { on: [] }, thresholds: {} };

test("tier id is provider/model@version", () => assert.equal(JEV.id, "fake-systemone/jev@1.14.0"));
test("tier rejects a non-exact version", () =>
  assert.throws(() => tier({ provider: "p", model: "m", version: "^1.0", camp: "systemone", questionTypes: ["noul"] }),
    (e: unknown) => e instanceof UrimError && e.type === "invalid_definition"));
test("definition is deeply frozen", () => {
  assert.ok(Object.isFrozen(triage));
  assert.ok(Object.isFrozen(triage.questions.team.options));
  assert.ok(Object.isFrozen(triage.tiers));
});
test("noul question carries yes/no labels", () =>
  assert.deepEqual(Object.keys(noul("q", { yes: "a", no: "b" }).options), ["yes", "no"]));
test("choice needs at least two options", () =>
  assert.throws(() => choice("q", { only: "x" }), (e: unknown) => e instanceof UrimError && e.type === "invalid_definition"));
test("threshold default outside 0..1 is rejected", () =>
  assert.throws(() => threshold({ on: "page", default: 1.5 }), (e: unknown) => e instanceof UrimError));
test("definition with no tiers is rejected", () =>
  assert.throws(() => defineDecision({ ...base, tiers: [], questions: { page: noul("q", { yes: "y", no: "n" }) } }),
    (e: unknown) => e instanceof UrimError && e.type === "invalid_definition"));
test("duplicate tiers are rejected", () =>
  assert.throws(() => defineDecision({ ...base, tiers: [JEV, JEV], questions: { page: noul("q", { yes: "y", no: "n" }) } }),
    (e: unknown) => e instanceof UrimError && /duplicate/.test(e.message)));
test("threshold on an unknown question is rejected", () =>
  assert.throws(() => defineDecision({ ...base, tiers: [JEV], questions: { page: noul("q", { yes: "y", no: "n" }) },
    thresholds: { t: threshold({ on: "nope" }) } }), (e: unknown) => e instanceof UrimError && /nope/.test(e.message)));
test("question type a tier cannot answer is rejected", () =>
  assert.throws(() => defineDecision({ ...base, tiers: [CLEF],
    questions: { s: { type: "score", prompt: "s", options: Object.freeze({ a: "a", b: "b" }) } } }),
    (e: unknown) => e instanceof UrimError && /score/.test(e.message)));
test("failover on a non-failover type is rejected", () =>
  assert.throws(() => defineDecision({ ...base, tiers: [JEV], questions: { page: noul("q", { yes: "y", no: "n" }) },
    failover: { on: ["auth"] } }), (e: unknown) => e instanceof UrimError && /auth/.test(e.message)));
