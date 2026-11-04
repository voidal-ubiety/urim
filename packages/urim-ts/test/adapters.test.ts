// Real HTTP adapters, exercised with a mocked fetch ONLY. No live call is ever made from tests.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createClient } from "../src/index.ts";
import { httpAdapter, openaiDecisions } from "../src/adapters/index.ts";
import { shippedAdapterNames, shippedAdapters } from "./shipped-adapters.ts";
import { DESCRIPTORS } from "../src/descriptors.ts";
import { FAKE_SYSTEMONE, FAKE_ENV } from "./fake-systemone.ts";
import { triage, severity, JEV } from "./fixtures.ts";
import { triageOk, dBody, dScore, dPredicate } from "./wire.ts";

const FAKE_KEY = "test-key-not-a-real-secret";
const fakeAdapter = () => httpAdapter(FAKE_SYSTEMONE);
type Call = { url: string; init: RequestInit };
const mockFetch = (status: number, body: unknown, headers: Record<string, string> = {}) => {
  const calls: Call[] = [];
  const fn = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init: init ?? {} });
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });
  }) as typeof fetch;
  return { fn, calls };
};
const silenceConsole = () => {
  const seen: string[] = [];
  const orig = { log: console.log, warn: console.warn, error: console.error, info: console.info, debug: console.debug };
  for (const k of Object.keys(orig) as Array<keyof typeof orig>) console[k] = (...a: unknown[]) => { seen.push(a.map(String).join(" ")); };
  return { seen, restore: () => Object.assign(console, orig) };
};

test("systemone adapter posts the systemone body with Bearer auth to the descriptor URL", async () => {
  const m = mockFetch(200, triageOk(0.9, "data", "jev-1.14.0"));
  const r = await createClient({ adapters: [fakeAdapter()], fetch: m.fn, env: { [FAKE_ENV]: FAKE_KEY } }).decide(triage, { report: "x" });
  assert.ok(r.ok);
  assert.equal(m.calls[0]?.url, FAKE_SYSTEMONE.url);
  const h = new Headers(m.calls[0]?.init.headers);
  assert.equal(h.get("authorization"), `Bearer ${FAKE_KEY}`);
  assert.equal(h.get("content-type"), "application/json");
  assert.equal(JSON.parse(String(m.calls[0]?.init.body)).model, "jev-1.14.0");
  assert.deepEqual([r.envelope.usage.inputTokens, r.envelope.usage.outputTokens], [1200, 3]);
});
test("openai adapter posts the decisions body to api.openai.com and records x-request-id", async () => {
  const levels = [{ value: 0, label: "low", probability: 0.1 }, { value: 1, label: "mid", probability: 0.2 }, { value: 2, label: "high", probability: 0.7 }];
  const m = mockFetch(200, dBody([dScore("sev", 1.6, 0.7, levels), dPredicate("page", 0.9)]), { "x-request-id": "req_42" });
  const r = await createClient({ adapters: [openaiDecisions(), fakeAdapter()], fetch: m.fn, env: { OPENAI_API_KEY: FAKE_KEY } }).decide(severity, { report: "x" });
  assert.ok(r.ok);
  assert.equal(m.calls[0]?.url, "https://api.openai.com/v1/decisions");
  assert.equal(new Headers(m.calls[0]?.init.headers).get("authorization"), `Bearer ${FAKE_KEY}`);
  assert.deepEqual(r.envelope.requestIds, { "openai/gpt-6-luna@0.0.0": "req_42" });
});
test("missing credential fails as auth without any network call, naming the env var only", async () => {
  const m = mockFetch(200, {});
  const r = await createClient({ adapters: [fakeAdapter()], fetch: m.fn, env: {} }).decide(triage, { report: "x" });
  assert.ok(!r.ok); assert.equal(r.error.type, "auth"); assert.match(r.error.message, /FAKE_SYSTEMONE_API_KEY/);
  assert.equal(m.calls.length, 0);
});
test("the credential never reaches console output or error messages", async () => {
  const quiet = silenceConsole();
  try {
    const m = mockFetch(401, { error: { message: "bad key" } });
    const r = await createClient({ adapters: [fakeAdapter()], fetch: m.fn, env: { [FAKE_ENV]: FAKE_KEY } }).decide(triage, { report: "x" });
    assert.ok(!r.ok); assert.equal(r.error.type, "auth");
    assert.ok(!JSON.stringify({ m: r.error.message, a: r.attempts }).includes(FAKE_KEY));
  } finally { quiet.restore(); }
  assert.ok(!quiet.seen.some((l) => l.includes(FAKE_KEY)));
});
test("systemone 529 maps to provider_unavailable and fails over", async () => {
  const m = mockFetch(529, { error: "overloaded" });
  const r = await createClient({ adapters: [fakeAdapter()], fetch: m.fn, env: { [FAKE_ENV]: FAKE_KEY } }).decide(triage, { report: "x" });
  assert.ok(!r.ok); assert.equal(r.attempts[0]?.outcome, "provider_unavailable");
});
test("a non-JSON reply body becomes nonconformant, not a crash", async () => {
  const fn = (async () => new Response("<html>", { status: 200 })) as typeof fetch;
  const r = await createClient({ adapters: [fakeAdapter()], fetch: fn, env: { [FAKE_ENV]: FAKE_KEY } }).decide(triage, { report: "x" });
  assert.ok(!r.ok); assert.equal(r.attempts[0]?.outcome, "nonconformant_response");
});
test("adapters are not exported from the main entry (opt-in import only)", async () => {
  const main = await import("../src/index.ts") as Record<string, unknown>;
  assert.ok(shippedAdapterNames.length >= 2);
  for (const n of shippedAdapterNames) assert.equal(main[n], undefined, n);
});
test("adapter only serves its own provider", () => assert.equal(fakeAdapter().provider, JEV.provider));
test("each shipped adapter is the HTTP adapter of its descriptor (one systemone, one decisions)", () => {
  const camps = shippedAdapters().map((a) => {
    const d = DESCRIPTORS[a.provider]!;
    assert.deepEqual([a.provider, a.credentialEnv], [d.provider, d.auth[0]!.env]);
    return d.camp;
  });
  assert.deepEqual([...camps].sort(), ["decisions", "systemone"]);
});
