// The five definition-of-done scenarios (design §1) end-to-end against fakeProvider, plus "no silent fallback".
import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { createClient, fakeProvider, defineDecision, noul, choice, threshold } from "../src/index.ts";
import type { FakeStep } from "../src/index.ts";
import { zodSchema } from "../src/zod.ts";
import { JEV, CLEF } from "./fixtures.ts";
import { s1Body, s1Noul, s1Choice } from "./wire.ts";

const triage = defineDecision({
  contract: "incident-triage@2.0.0",
  tiers: [JEV, CLEF],
  input: zodSchema(z.object({ report: z.string().max(16_000) })),
  questions: {
    page: noul("Should someone be paged right now?", { yes: "Active impact", no: "No impact" }),
    team: choice("Which team owns this incident?", { billing: "b", platform: "p", identity: "i", data: "d" }),
  },
 
  failover: { on: ["timeout", "provider_unavailable", "rate_limited", "budget"] },
  thresholds: {
    page_oncall: threshold({ on: "page", default: 0.8 }),  // PLACEHOLDER
    auto_route: threshold({ on: "team", default: 0.6 }),   // PLACEHOLDER
  },
  interpret: ({ answers, cut }) => ({
    page: answers.page.value === "yes" && cut.page_oncall.passes,
    team: cut.auto_route.passes ? answers.team.value : null,
  }),
});
const sample = { report: "checkout 500s since deploy" };
const reply = (teamConf: number): FakeStep => ({ body: s1Body({ page: s1Noul(0.955), team: s1Choice("billing", teamConf, { billing: 0.9, platform: 0.04, identity: 0.03, data: 0.03 }) }) });

test("DoD 1: success on the primary tier", async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [reply(0.9)] })] }).decide(triage, sample);
  assert.ok(r.ok);
  assert.deepEqual(r.value, { page: true, team: "billing" });
  assert.equal(r.fallback, null);
  assert.equal(r.envelope.tier.role, "primary");
});
test("DoD 2: failover on timeout is reported", async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [{ fail: "timeout" }], [CLEF.id]: [reply(0.9)] })] }).decide(triage, sample);
  assert.ok(r.ok);
  assert.deepEqual(r.fallback, { from: JEV.id, reason: "timeout", attempts: 1 });
});
test("DoD 3: abstain when all tiers fail", async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [{ fail: "provider_unavailable" }], [CLEF.id]: [{ fail: "rate_limited" }] })] }).decide(triage, sample);
  assert.ok(!r.ok);
  assert.equal(r.error.type, "all_tiers_failed");
  assert.deepEqual(r.attempts.map((a) => a.outcome), ["provider_unavailable", "rate_limited"]);
});
test("DoD 4: below-threshold confidence escalates (team null)", async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [reply(0.3)] })] }).decide(triage, sample);
  assert.ok(r.ok);
  assert.equal(r.value.team, null);
  assert.equal(r.thresholds.auto_route.passes, false);
});
test("DoD 5: cancellation returns cancelled and never fails over", async () => {
  const fake = fakeProvider({ [JEV.id]: [{ hang: true }], [CLEF.id]: [reply(0.9)] });
  const ctl = new AbortController();
  const pending = createClient({ adapters: [fake] }).decide(triage, sample, { signal: ctl.signal });
  setTimeout(() => ctl.abort(), 5);
  const r = await pending;
  assert.ok(!r.ok && r.error.type === "cancelled");
  assert.equal(fake.calls.length, 1);
});
test("no silent fallback: any non-primary answer carries fallback (all failure orders)", async () => {
  const fails = ["timeout", "provider_unavailable", "rate_limited", "quota_exceeded", "nonconformant_response"] as const;
  for (const f of fails) {
    const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [{ fail: f }], [CLEF.id]: [reply(0.9)] })] }).decide(triage, sample);
    if (r.ok && r.envelope.tier.id !== JEV.id) assert.notEqual(r.fallback, null, f);
  }
});
