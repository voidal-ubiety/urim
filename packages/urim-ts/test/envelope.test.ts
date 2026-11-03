import { test } from "node:test";
import assert from "node:assert/strict";
import { resolveCuts, buildEnvelope, UrimError } from "../src/index.ts";
import type { Answers, Lock } from "../src/index.ts";
import { triage, JEV, CLEF, prices } from "./fixtures.ts";

const answers: Answers = {
  page: { value: "yes", confidence: 0.9, native: { name: "page", value: "yes", confidence: 0.9 } },
  team: { value: "billing", confidence: null, native: { name: "team", value: "billing", confidence: null } },
};
const lock: Lock = { lock: 1, contract: { id: triage.contract, hash: "sha256:PLACEHOLDER" },
  cuts: { page_oncall: { [CLEF.id]: 0.95 }, auto_route: { [JEV.id]: 0.5 } } };

test("default cut used when lock has none for this tier", () =>
  assert.deepEqual(resolveCuts(triage, JEV, answers, { mode: "dev", lock }).page_oncall,
    { value: 0.8, source: "default", passes: true, confidence: 0.9 }));
test("lock cut for the answering tier wins over default", () =>
  assert.equal(resolveCuts(triage, CLEF, answers, { mode: "dev", lock }).page_oncall?.source, "lock"));
test("lock cut below confidence fails", () =>
  assert.equal(resolveCuts(triage, CLEF, answers, { mode: "dev", lock }).page_oncall?.passes, false));
test("missing confidence with a cut escalates", () =>
  assert.deepEqual(resolveCuts(triage, JEV, answers, { mode: "dev", lock }).auto_route,
    { value: 0.5, source: "lock", passes: false, confidence: null }));
test("no cutoff in dev passes through with source none", () =>
  assert.deepEqual(resolveCuts(triage, CLEF, answers, { mode: "dev" }).auto_route,
    { value: null, source: "none", passes: true, confidence: null }));
test("no cutoff in prod is a lock_violation", () =>
  assert.throws(() => resolveCuts(triage, CLEF, answers, { mode: "prod" }),
    (e: unknown) => e instanceof UrimError && e.type === "lock_violation"));

const env = (role: "primary" | "fallback", raw?: unknown) => buildEnvelope({
  def: triage, contractHash: "sha256:PLACEHOLDER", tier: role === "primary" ? JEV : CLEF, answers,
  cuts: resolveCuts(triage, role === "primary" ? JEV : CLEF, answers, { mode: "dev" }),
  attempts: role === "primary" ? [{ tier: JEV.id, outcome: "ok", latencyMs: 5 }]
    : [{ tier: JEV.id, outcome: "timeout", latencyMs: 900 }, { tier: CLEF.id, outcome: "ok", latencyMs: 5 }],
  requestIds: {}, at: "2026-10-28T20:00:00.000Z", prices, ...(raw === undefined ? {} : { raw }),
});

test("primary answer has no fallback", () => assert.equal(env("primary").fallback, null));
test("non-primary answer always reports fallback", () =>
  assert.deepEqual(env("fallback").fallback, { from: JEV.id, reason: "timeout", attempts: 1 }));
test("envelope is deeply frozen and marks role", () => {
  const e = env("fallback");
  assert.ok(Object.isFrozen(e) && Object.isFrozen(e.answers.page));
  assert.equal(e.tier.role, "fallback");
});
test("raw is omitted unless provided", () => {
  assert.equal("raw" in env("primary"), false);
  assert.deepEqual(env("primary", { a: 1 }).raw, { a: 1 });
});
test("cost estimated from dated price table when provider reports none", () =>
  assert.deepEqual(env("primary").usage.cost,
    { amount: 0.004, currency: "USD", source: "estimated", priceTable: { id: "fixture-prices", asOf: "2026-10-28", url: "https://example.invalid/PLACEHOLDER" } }));
test("cost is null when no price is known", () =>
  assert.equal(buildEnvelope({ def: triage, contractHash: "h", tier: CLEF, answers, cuts: {}, attempts: [],
    requestIds: {}, at: "t" }).usage.cost, null));
