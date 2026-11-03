import { test } from "node:test";
import assert from "node:assert/strict";
import { createClient, fakeProvider, defineDecision, emit, UrimError } from "../src/index.ts";
import type { Lock, Settled } from "../src/index.ts";
import { triage, JEV, CLEF, prices } from "./fixtures.ts";
import { triageOk } from "./wire.ts";

const ok = { body: triageOk() };
const input = { report: "db down" };
const goodLock = (): Lock => ({ lock: 1, contract: { id: triage.contract, hash: emit(triage).hash },
  cuts: { auto_route: { [JEV.id]: 0.5, [CLEF.id]: 0.5 } } });
const isType = (t: string) => (e: unknown) => e instanceof UrimError && e.type === t;

// --- startup checks (D4/D6) ---
test("prod without a lock is a startup error", () =>
  assert.throws(() => createClient({ adapters: [fakeProvider({})], mode: "prod", decisions: [triage] }), isType("lock_violation")));
test("prod with a hash mismatch is a startup error", () =>
  assert.throws(() => createClient({ adapters: [fakeProvider({})], mode: "prod", decisions: [triage],
    locks: [{ ...goodLock(), contract: { id: triage.contract, hash: "sha256:stale" } }] }), isType("lock_violation")));
test("prod with a missing cutoff is a startup error", () =>
  assert.throws(() => createClient({ adapters: [fakeProvider({})], mode: "prod", decisions: [triage],
    locks: [{ ...goodLock(), cuts: { auto_route: { [JEV.id]: 0.5 } } }] }), (e: unknown) => isType("lock_violation")(e) && /auto_route/.test((e as Error).message)));
test("prod with a good lock starts", () =>
  assert.doesNotThrow(() => createClient({ adapters: [fakeProvider({})], mode: "prod", decisions: [triage], locks: [goodLock()] })));
test("dev with no lock starts", () => assert.doesNotThrow(() => createClient({ adapters: [], decisions: [triage] })));
test("prod decide on an unregistered decision abstains with lock_violation", async () => {
  const c = createClient({ adapters: [fakeProvider({})], mode: "prod", decisions: [], locks: [] });
  const r = await c.decide(triage, input);
  assert.ok(!r.ok && r.error.type === "lock_violation");
});

// --- loop ---
test("invalid input abstains with invalid_input and makes no call", async () => {
  const fake = fakeProvider({});
  const r = await createClient({ adapters: [fake] }).decide(triage, { report: 3 } as unknown as { report: string });
  assert.ok(!r.ok && r.error.type === "invalid_input");
  assert.equal(fake.calls.length, 0);
});
test("prepare runs before encode", async () => {
  const fake = fakeProvider({ [JEV.id]: [ok] });
  const def = defineDecision({ ...triage, prepare: (i: { report: string }) => ({ report: i.report.toUpperCase() }) });
  await createClient({ adapters: [fake] }).decide(def, input);
  assert.deepEqual((fake.calls[0]?.body as { state: unknown }).state, { report: "DB DOWN" });
});
test("non-failover error abstains without trying the next tier", async () => {
  const fake = fakeProvider({ [JEV.id]: [{ fail: "auth" }] });
  const r = await createClient({ adapters: [fake] }).decide(triage, input);
  assert.ok(!r.ok && r.error.type === "auth");
  assert.equal(fake.calls.length, 1);
});
test("unexpected adapter exception becomes internal and abstains", async () => {
  const r = await createClient({ adapters: [fakeProvider({})] }).decide(triage, input);
  assert.ok(!r.ok && r.error.type === "internal" && r.error.cause instanceof Error);
});
test("deadline hit is a timeout failure that fails over when listed", async () => {
  // Deterministic: an injected clock that reads 0 until the deadline abort fires, then exactly the deadline.
  // (With Date.now the abort timer could fire while the clock still read < 30 ms, leaving CLEF time to answer.)
  let t = 0;
  const fake = fakeProvider({ [JEV.id]: [{ hang: true }], [CLEF.id]: [ok] });
  const clocked = { provider: fake.provider, send: (req: Parameters<typeof fake.send>[0], io: Parameters<typeof fake.send>[1]) => {
    io.signal.addEventListener("abort", () => { t = 30; }, { once: true });
    return fake.send(req, io);
  } };
  const r = await createClient({ adapters: [clocked], now: () => t }).decide(triage, input, { deadlineMs: 30 });
  // CLEF also gets the exhausted deadline: it fails as timeout without a call
  assert.ok(!r.ok && r.error.type === "all_tiers_failed");
  assert.deepEqual(r.attempts.map((a) => a.outcome), ["timeout", "timeout"]);
  assert.equal(fake.calls.length, 1);
});
test("deadline timer firing while the clock still reads under the deadline ends the chain (early-fire race)", async () => {
  // Frozen clock: measured elapsed time stays 0, so only the fired timer says the deadline is spent.
  const fake = fakeProvider({ [JEV.id]: [{ hang: true }], [CLEF.id]: [ok] });
  const r = await createClient({ adapters: [fake], now: () => 0 }).decide(triage, input, { deadlineMs: 5 });
  assert.ok(!r.ok && r.error.type === "all_tiers_failed");
  assert.deepEqual(r.attempts.map((a) => a.outcome), ["timeout", "timeout"]);
  assert.deepEqual(fake.calls.map((c) => c.tierId), [JEV.id]);
});
test("an adapter's own timeout error does not spend the deadline", async () => {
  const fake = fakeProvider({ [JEV.id]: [{ fail: "timeout" }], [CLEF.id]: [ok] });
  const r = await createClient({ adapters: [fake], now: () => 0 }).decide(triage, input, { deadlineMs: 1000 });
  assert.ok(r.ok);
  assert.deepEqual(fake.calls.map((c) => c.tierId), [JEV.id, CLEF.id]);
});
// --- client-wide default deadline ---
test("createClient rejects a deadlineMs that is not a finite number > 0", () => {
  for (const bad of [0, -1, Number.NaN, Number.POSITIVE_INFINITY, "5"]) {
    assert.throws(() => createClient({ adapters: [], deadlineMs: bad as number }), isType("invalid_definition"), String(bad));
  }
});
test("client deadlineMs applies when the call sets none", async () => {
  const fake = fakeProvider({ [JEV.id]: [{ hang: true }], [CLEF.id]: [ok] });
  const r = await createClient({ adapters: [fake], now: () => 0, deadlineMs: 5 }).decide(triage, input);
  assert.ok(!r.ok && r.error.type === "all_tiers_failed");
  assert.deepEqual(r.attempts.map((a) => a.outcome), ["timeout", "timeout"]);
  assert.deepEqual(fake.calls.map((c) => c.tierId), [JEV.id]);
});
test("per-call deadlineMs overrides the client default", async () => {
  const fake = fakeProvider({ [JEV.id]: [ok] });
  const r = await createClient({ adapters: [fake], now: () => 0, deadlineMs: 1000 }).decide(triage, input, { deadlineMs: 0 });
  assert.ok(!r.ok);
  assert.deepEqual(r.attempts.map((a) => a.outcome), ["timeout", "timeout"]);
  assert.equal(fake.calls.length, 0);
});
test("per-call deadlineMs: null opts out of the client default", async () => {
  const fake = fakeProvider({ [JEV.id]: [ok, ok] });
  const slow = { provider: fake.provider, send: async (req: Parameters<typeof fake.send>[0], io: Parameters<typeof fake.send>[1]) => {
    await new Promise((r) => setTimeout(r, 30));
    return fake.send(req, io);
  } };
  const c = createClient({ adapters: [slow], deadlineMs: 5 });
  assert.ok(!(await c.decide(triage, input)).ok);
  assert.ok((await c.decide(triage, input, { deadlineMs: null })).ok);
});
test("explain shows the effective deadline", () => {
  assert.ok(!("deadlineMs" in createClient({ adapters: [] }).explain(triage)));
  const c = createClient({ adapters: [], deadlineMs: 5 });
  assert.equal(c.explain(triage).deadlineMs, 5);
  assert.equal(c.explain(triage, { deadlineMs: 50 }).deadlineMs, 50);
  assert.ok(!("deadlineMs" in c.explain(triage, { deadlineMs: null })));
});
test("budget skip is recorded and the next tier answers with fallback reason budget", async () => {
  const fake = fakeProvider({ [CLEF.id]: [ok] });
  const r = await createClient({ adapters: [fake], prices, budget: { maxCost: 0.002, currency: "USD" } }).decide(triage, input);
  assert.ok(r.ok);
  assert.deepEqual(r.fallback, { from: JEV.id, reason: "budget", attempts: 1 });
  assert.equal(r.envelope.attempts[0]?.outcome, "skipped_budget");
});
test("raw is omitted by default", async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [ok] })] }).decide(triage, input);
  assert.ok(r.ok && !("raw" in r.envelope));
});
test("raw per call", async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [ok] })] }).decide(triage, input, { raw: true });
  assert.ok(r.ok);
  assert.deepEqual(r.envelope.raw, ok.body);
});
test("raw per client, overridable per call", async () => {
  const c = createClient({ adapters: [fakeProvider({ [JEV.id]: [ok, ok] })], raw: true });
  const a = await c.decide(triage, input);
  const b = await c.decide(triage, input, { raw: false });
  assert.ok(a.ok && "raw" in a.envelope && b.ok && !("raw" in b.envelope));
});
test("decideOrThrow throws the UrimError on abstain", async () =>
  assert.rejects(createClient({ adapters: [fakeProvider({ [JEV.id]: [{ fail: "auth" }] })] }).decideOrThrow(triage, input), isType("auth")));
test("client explain uses client budget and prices", () => {
  const c = createClient({ adapters: [], prices, budget: { maxCost: 0.002, currency: "USD" } });
  assert.equal(c.explain(triage).steps[0]?.action, "skip");
});

// --- D11 ---
test("interpret error is rethrown as-is, no fallback, envelope marked interpret_failed", async () => {
  const boom = new TypeError("bug in interpret");
  const seen: Settled[] = [];
  const fake = fakeProvider({ [JEV.id]: [ok], [CLEF.id]: [ok] });
  const c = createClient({ adapters: [fake], onSettled: (e) => { seen.push(e); } });
  const def = defineDecision({ ...triage, interpret: () => { throw boom; } });
  await assert.rejects(c.decide(def, input), (e: unknown) => e === boom);
  await c.flush();
  assert.equal(fake.calls.length, 1);
  assert.equal(seen[0]?.outcome, "interpret_failed");
  assert.equal(seen[0]?.envelope?.interpretFailed, true);
});

// --- D3 ---
test("onSettled gets a frozen ok record carrying the result envelope", async () => {
  const seen: Settled[] = [];
  const c = createClient({ adapters: [fakeProvider({ [JEV.id]: [ok] })], onSettled: (e) => { seen.push(e); } });
  const r = await c.decide(triage, input);
  await c.flush();
  assert.ok(r.ok && seen[0]?.envelope === r.envelope && Object.isFrozen(seen[0]));
  assert.equal(seen[0]?.outcome, "ok");
  assert.equal(seen[0]?.error, null);
});
test("onSettled throwing goes to onHookError once and never reaches the caller", async () => {
  const errors: unknown[] = [];
  const c = createClient({ adapters: [fakeProvider({ [JEV.id]: [ok] })],
    onSettled: () => { throw new Error("telemetry down"); }, onHookError: (err) => { errors.push(err); } });
  const r = await c.decide(triage, input);
  await c.flush();
  assert.ok(r.ok);
  assert.equal(errors.length, 1);
});
test("flush awaits async hooks", async () => {
  let done = false;
  const c = createClient({ adapters: [fakeProvider({ [JEV.id]: [ok] })],
    onSettled: async () => { await new Promise((r) => setTimeout(r, 10)); done = true; } });
  await c.decide(triage, input);
  assert.equal(done, false);
  await c.flush();
  assert.equal(done, true);
});

// --- fix 1: onSettled fires on every settled call, uniform frozen record ---
const record = async (c: (on: (s: Settled) => void) => ReturnType<typeof createClient>, run: (cl: ReturnType<typeof createClient>) => Promise<unknown>) => {
  const seen: Settled[] = [];
  const cl = c((s) => { seen.push(s); });
  await run(cl).catch(() => undefined);
  await cl.flush();
  return seen;
};
const abstainCases: Array<[string, Record<string, Array<{ fail: "auth" | "timeout" | "provider_unavailable" }>>, unknown, string]> = [
  ["non-failover abstain", { [JEV.id]: [{ fail: "auth" }] }, input, "auth"],
  ["all_tiers_failed", { [JEV.id]: [{ fail: "timeout" }], [CLEF.id]: [{ fail: "provider_unavailable" }] }, input, "all_tiers_failed"],
  ["invalid_input", {}, { report: 1 }, "invalid_input"],
];
for (const [name, script, inp, type] of abstainCases) {
  test(`onSettled fires on ${name} with a frozen abstain record`, async () => {
    const seen = await record((on) => createClient({ adapters: [fakeProvider(script)], onSettled: on }),
      (c) => c.decide(triage, inp as { report: string }));
    assert.equal(seen.length, 1);
    const s = seen[0]!;
    assert.ok(Object.isFrozen(s) && Object.isFrozen(s.attempts));
    assert.deepEqual([s.settled, s.outcome, s.envelope, s.error?.type, s.contract.id], ["urim/1", "abstain", null, type, triage.contract]);
  });
}
test("settled records share one key set across outcomes", async () => {
  const keys = async (script: Record<string, Array<{ fail: "auth" } | typeof ok>>) =>
    Object.keys((await record((on) => createClient({ adapters: [fakeProvider(script)], onSettled: on }), (c) => c.decide(triage, input)))[0]!).sort();
  assert.deepEqual(await keys({ [JEV.id]: [ok] }), await keys({ [JEV.id]: [{ fail: "auth" }] }));
});
test("onHookError receives the settled record", async () => {
  const got: Settled[] = [];
  const c = createClient({ adapters: [fakeProvider({ [JEV.id]: [{ fail: "auth" }] })],
    onSettled: () => { throw new Error("x"); }, onHookError: (_e, s) => { got.push(s); } });
  await c.decide(triage, input);
  await c.flush();
  assert.equal(got[0]?.outcome, "abstain");
});

// --- fix 2: prod startup fails when a tier's provider has no adapter ---
test("prod: registered tier with no adapter is a startup invalid_definition", () =>
  assert.throws(() => createClient({ adapters: [], mode: "prod", decisions: [triage], locks: [goodLock()] }),
    (e: unknown) => isType("invalid_definition")(e) && /cloudflare/.test((e as Error).message) && /typesafe/.test((e as Error).message)));
test("prod: a wildcard (test) adapter satisfies the check", () =>
  assert.doesNotThrow(() => createClient({ adapters: [fakeProvider({})], mode: "prod", decisions: [triage], locks: [goodLock()] })));
test("dev: missing adapter is still decide-time invalid_definition", async () => {
  const c = createClient({ adapters: [], decisions: [triage] });
  const r = await c.decide(triage, input);
  assert.ok(!r.ok && r.error.type === "invalid_definition");
});
