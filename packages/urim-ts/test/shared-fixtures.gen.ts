// Generates packages/shared-fixtures/*.vectors.json from the TS reference implementation.
// Run: node test/shared-fixtures.gen.ts   (shared-fixtures.test.ts fails if the files are stale)
import { readFileSync, writeFileSync } from "node:fs";
import { UrimError, canonicalize, createClient, decodeReply, defineDecision, emit, encodeRequest, estimateInputTokens, fakeProvider, parseLock, serializeLock, sha256, threshold } from "../src/index.ts";
import type { Definition, FakeStep, Lock } from "../src/index.ts";
import { accuracy, brier, escalationAt, fitCutoff, flipRate, percentile, precisionAt, stdev, type Scored } from "../src/fit-math.ts";
import { estimateFitCost, parseCases, runFit } from "../src/fit.ts";
import { main, type CliIo } from "../src/cli.ts";
import { httpAdapter } from "../src/adapters/index.ts";
import { DESCRIPTORS } from "../src/descriptors.ts";
import { FAKE_SYSTEMONE } from "./fake-systemone.ts";
import { gate } from "./fixtures/fit.decision.ts";
import { prices, severity, triage, CLEF, JEV, OPENAI } from "./fixtures.ts";
import { dBody, dChoice, dPredicate, dRefusal, dScore, s1Body, s1Choice, s1Noul, s1Score, triageOk } from "./wire.ts";

const shared = new URL("../../shared-fixtures/", import.meta.url);
const inputs = JSON.parse(readFileSync(new URL("canonical.inputs.json", shared), "utf8")) as { name: string; value: unknown }[];

export const canonicalVectors = () => inputs.map(({ name, value }) => {
  const json = canonicalize(value);
  return { name, json, hash: sha256(json) };
});

const sevProbs = [{ value: 0, label: "low", probability: 0.1 }, { value: 1, label: "mid", probability: 0.2 }, { value: 2, label: "high", probability: 0.7 }];
const cases: { name: string; def: "triage" | "severity"; tier: "JEV" | "OPENAI"; status?: number; headers?: Record<string, string>; body: unknown }[] = [
  { name: "systemone triage ok", def: "triage", tier: "JEV", body: triageOk() },
  { name: "systemone tie 0.5", def: "triage", tier: "JEV", body: s1Body({ page: s1Noul(0.5), team: s1Choice("data", 0.4, { data: 0.9 }) }) },
  { name: "systemone label outside", def: "triage", tier: "JEV", body: s1Body({ page: s1Noul(0.2), team: s1Choice("nope", 0.4, { data: 0.9 }) }) },
  { name: "systemone stray model", def: "triage", tier: "JEV", body: triageOk(0.9, "data", "jev-9") },
  { name: "systemone score", def: "severity", tier: "JEV", body: s1Body({ sev: s1Score(1.6, 0.55, { "0": 0.1, "1": 0.2, "2": 0.7 }, { "0": "low", "1": "mid", "2": "high" }), page: s1Noul(0.05) }) },
  { name: "fake-systemone 529", def: "triage", tier: "JEV", status: 529, body: { error: { message: "overloaded" } } },
  { name: "decisions ok", def: "severity", tier: "OPENAI", headers: { "X-Request-Id": "req_1" }, body: dBody([dScore("sev", 2, 0.7, sevProbs), dPredicate("page", 0.8)]) },
  { name: "decisions null names", def: "severity", tier: "OPENAI", body: dBody([dScore(null, 2, 0.7, sevProbs), dPredicate(null, 0.3)]) },
  { name: "decisions refusal", def: "severity", tier: "OPENAI", body: dBody([dRefusal("sev"), dPredicate("page", 0.8)]) },
  { name: "decisions boolean choice", def: "severity", tier: "OPENAI", body: dBody([dChoice("sev", true, 0.9, []), dPredicate("page", 0.8)]) },
  { name: "openai 429 quota", def: "severity", tier: "OPENAI", status: 429, headers: { "retry-after": "7", "x-request-id": "req_q" }, body: { error: { code: "credit_balance_exhausted" } } },
  { name: "openai 429 rate", def: "severity", tier: "OPENAI", status: 429, body: { error: { code: "rate_limit_exceeded" } } },
];
const defs = { triage, severity } as const;
const tiers = { JEV, OPENAI } as const;

export const codecVectors = () => ({
  contracts: { triage: emit(triage).hash, severity: emit(severity).hash },
  encode: (["triage", "severity"] as const).flatMap((d) => (["JEV", "OPENAI"] as const).map((t) => {
    const req = encodeRequest(defs[d], tiers[t], { report: "db primary unreachable — since 02:00 ✓" });
    return { def: d, tier: t, input: { report: "db primary unreachable — since 02:00 ✓" }, url: req.url, path: req.path,
      body: req.body, estimatedInputTokens: estimateInputTokens(req) };
  })),
  decode: cases.map((c) => {
    const r = decodeReply(defs[c.def], tiers[c.tier], { status: c.status ?? 200, headers: c.headers ?? {}, body: c.body, latencyMs: 0 });
    return { ...c, expected: r.ok ? { ok: true, answers: r.answers, usage: r.usage, model: r.model }
      : { ok: false, type: r.error.type, requestId: r.error.requestId ?? null, retryAfterMs: r.error.retryAfterMs ?? null } };
  }),
});

// ---- slice 6: lock, fit math, fit runner, client scenarios ----
const H = `sha256:${"a".repeat(64)}`;
const fullLock = {
  lock: 1, contract: { id: "c@1.0.0", hash: H },
  tiers: [{ id: "fake-systemone/jev@1.14.0", descriptorHash: null }, { id: "cloudflare/clef-flash@x.y.z", descriptorHash: H }],
  cuts: { gate: { "fake-systemone/jev@1.14.0": 0.6 }, "b_é": { "z": 0, "a": 1 } },
  eval: { setHash: H, n: 5, repeat: 2, at: "2026-10-28T21:00:00.000Z", objectivesMet: true },
};
const lockInputs: [string, unknown][] = [
  ["full", fullLock],
  ["minimal", { lock: 1, contract: { id: "c", hash: H }, cuts: {} }],
  ["unknown keys ignored", { ...fullLock, futureField: 1, contract: { ...fullLock.contract, extra: true } }],
  ["wrong format version", { ...fullLock, lock: 2 }],
  ["hash without sha256 prefix", { ...fullLock, contract: { id: "c", hash: "abc" } }],
  ["cut outside 0..1", { ...fullLock, cuts: { gate: { t: 1.5 } } }],
  ["cut not a number", { ...fullLock, cuts: { gate: { t: "0.5" } } }],
  ["cuts not an object", { ...fullLock, cuts: [] }],
  ["tiers not an array", { ...fullLock, tiers: {} }],
  ["tier descriptorHash bad", { ...fullLock, tiers: [{ id: "x", descriptorHash: "nope" }] }],
  ["eval.n negative", { ...fullLock, eval: { ...fullLock.eval, n: -1 } }],
  ["eval.repeat zero", { ...fullLock, eval: { ...fullLock.eval, repeat: 0 } }],
  ["many problems", { lock: 3, contract: null, cuts: 5 }],
  ["not an object", "lock"],
];
export const lockVectors = () => lockInputs.map(([name, input]) => {
  const r = parseLock(input);
  return r.ok ? { name, input, ok: true, lock: r.lock, text: serializeLock(r.lock) }
    : { name, input, ok: false, issuePaths: r.issues.map((i) => i.path) };
});

const S = (pairs: [number | null, boolean][]): Scored[] => pairs.map(([confidence, correct]) => ({ confidence, correct }));
const scoredSets: [string, Scored[]][] = [
  ["hand", S([[0.9, true], [0.8, true], [0.7, false], [0.6, true], [0.5, false]])],
  ["with nulls and ties", S([[null, true], [0.5, true], [0.5, false], [0.25, true], [1, true], [null, false], [0.75, false]])],
  ["all correct", S([[0.1, true], [0.3, true], [0.2, true]])],
  ["empty", []],
  ["float noise", S([[0.1 + 0.2, true], [0.3, false], [0.7000000000000001, true], [1 / 3, true]])],
];
const objectives = [{}, { minPrecision: 0.75 }, { escalationRate: 0.4 }, { minPrecision: 0.6, escalationRate: 0.5 },
  { minPrecision: 0.9, escalationRate: 0.1 }, { minPrecision: 1.01 }, { escalationRate: 0 }];
export const fitMathVectors = () => ({
  fitCutoff: scoredSets.flatMap(([name, xs]) => objectives.map((objective) => ({ name, xs, objective, expected: fitCutoff(xs, objective) }))),
  stats: scoredSets.map(([name, xs]) => ({ name, xs, accuracy: accuracy(xs), brier: brier(xs),
    precisionAt: [0, 0.5, 0.8, 1].map((c) => precisionAt(xs, c)), escalationAt: [0, 0.5, 0.8, 1].map((c) => escalationAt(xs, c)) })),
  flipRate: [[["a", "b"], ["a", "c"]], [["x"], ["x"], ["y"]], [], [[], []], [["a", "a", "a"]]].map((runs) => ({ runs, expected: flipRate(runs) })),
  stdev: [[], [1], [1, 2, 3, 4], [0.1, 0.2, 0.7]].map((xs) => ({ xs, expected: stdev(xs) })),
  percentile: [[[], 50], [[5], 95], [[3, 1, 2], 50], [[10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 95], [[1, 2, 3, 4], 50], [[4, 1, 3, 2], 0], [[1, 2], 100]]
    .map(([xs, p]) => ({ xs, p, expected: percentile(xs as number[], p as number) })),
});

const fitCases = parseCases(readFileSync(new URL("./fixtures/eval.fit.jsonl", import.meta.url), "utf8"));
const fitScript = JSON.parse(readFileSync(new URL("./fixtures/fake.fit.json", import.meta.url), "utf8")) as Record<string, FakeStep[]>;
const fixedNow = () => Date.parse("2026-10-28T21:00:00.000Z");
export const fitRunVectors = async () => {
  const strict = defineDecision({ ...gate, thresholds: { gate: threshold({ on: "page", objective: { minPrecision: 1.01 } }) } });
  const out = [];
  for (const [name, def, repeat, yes, p] of [["ok repeat 1", gate, 1, true, prices], ["ok repeat 2", gate, 2, true, prices],
    ["needs confirmation", gate, 1, false, prices], ["unmet", strict, 1, true, prices],
    ["unknown price", gate, 1, true, { ...prices, entries: {} }]] as const) {
    const r = await runFit({ def, cases: fitCases, adapters: [fakeProvider(fitScript, { cycle: true })], prices: p, repeat, yes, now: fixedNow });
    out.push({ name, def: def === gate ? "gate" : "strict", repeat, yes, prices: p, expected: JSON.parse(JSON.stringify(r)),
      lockText: r.status === "ok" ? serializeLock(r.lock) : null });
  }
  return { cases: fitCases, script: fitScript, runs: out, estimate: estimateFitCost(gate, 5, 2, prices) };
};

// Client scenarios: fake replies, fixed clock (latency 0), envelopes compared as JSON.
type Scenario = { name: string; def: "triage" | "severity"; script: Record<string, FakeStep[]>; input: unknown;
  deps?: { mode?: "prod"; budget?: { maxCost: number; currency: string }; prices?: boolean; raw?: boolean; lock?: boolean; deadlineMs?: number };
  opts?: { raw?: boolean; deadlineMs?: number | null; budget?: { maxCost: number; currency: string } } };
const ok1 = () => ({ body: triageOk() });
const sevOk = () => ({ body: s1Body({ sev: s1Score(1.6, 0.55, { "0": 0.1, "1": 0.2, "2": 0.7 }, { "0": "low", "1": "mid", "2": "high" }), page: s1Noul(0.05) }) });
const scenarios: Scenario[] = [
  { name: "primary ok", def: "triage", script: { [JEV.id]: [ok1()] }, input: { report: "x" }, deps: { prices: true } },
  { name: "failover provider_unavailable", def: "triage", script: { [JEV.id]: [{ fail: "provider_unavailable" }], [CLEF.id]: [ok1()] }, input: { report: "x" }, deps: { prices: true } },
  { name: "failover on HTTP 529", def: "triage", script: { [JEV.id]: [{ status: 529, body: { error: {} } }], [CLEF.id]: [ok1()] }, input: { report: "x" } },
  { name: "non-failover error abstains", def: "triage", script: { [JEV.id]: [{ fail: "auth" }], [CLEF.id]: [ok1()] }, input: { report: "x" } },
  { name: "nonconformant abstains", def: "triage", script: { [JEV.id]: [{ body: { nope: 1 } }] }, input: { report: "x" } },
  { name: "all tiers failed", def: "triage", script: { [JEV.id]: [{ fail: "timeout" }], [CLEF.id]: [{ fail: "rate_limited" }] }, input: { report: "x" } },
  { name: "budget skip with per-call price", def: "triage", script: { [CLEF.id]: [ok1()] }, input: { report: "x" }, deps: { prices: true, budget: { maxCost: 0.002, currency: "USD" } } },
  { name: "budget per call option", def: "triage", script: { [CLEF.id]: [ok1()] }, input: { report: "x" }, deps: { prices: true }, opts: { budget: { maxCost: 0.002, currency: "USD" } } },
  { name: "budget skips everything", def: "triage", script: {}, input: { report: "x" }, deps: { prices: true, budget: { maxCost: 0.0001, currency: "USD" } } },
  { name: "invalid input", def: "triage", script: {}, input: { report: 3 } },
  { name: "raw opt-in per call", def: "triage", script: { [JEV.id]: [ok1()] }, input: { report: "x" }, opts: { raw: true } },
  { name: "raw opt-in on client", def: "triage", script: { [JEV.id]: [ok1()] }, input: { report: "x" }, deps: { raw: true } },
  { name: "severity timeout fails over", def: "severity", script: { [OPENAI.id]: [{ fail: "timeout" }], [JEV.id]: [sevOk()] }, input: { report: "x" } },
  { name: "severity openai ok", def: "severity", script: { [OPENAI.id]: [{ body: dBody([dScore("sev", 1.6, 0.7, sevProbs), dPredicate("page", 0.9)]) }] }, input: { report: "x" } },
  { name: "severity rate_limited abstains", def: "severity", script: { [OPENAI.id]: [{ fail: "rate_limited" }] }, input: { report: "x" } },
  // early-fire race: the clock is frozen, so only the fired deadline timer can stop CLEF from being called
  { name: "deadline fires under a frozen clock", def: "triage", script: { [JEV.id]: [{ hang: true }], [CLEF.id]: [ok1()] }, input: { report: "x" }, opts: { deadlineMs: 5 } },
  { name: "client deadline applies under a frozen clock", def: "triage", script: { [JEV.id]: [{ hang: true }], [CLEF.id]: [ok1()] }, input: { report: "x" }, deps: { deadlineMs: 5 } },
  { name: "per-call deadline overrides the client default", def: "triage", script: { [JEV.id]: [ok1()] }, input: { report: "x" }, deps: { deadlineMs: 1000 }, opts: { deadlineMs: 0 } },
  { name: "prod with lock uses locked cut", def: "triage", script: { [JEV.id]: [ok1()] }, input: { report: "x" }, deps: { mode: "prod", lock: true } },
];
const lockFor = (def: Definition<any, any, any, any>): Lock => ({ lock: 1, contract: { id: def.contract, hash: emit(def).hash },
  cuts: { auto_route: { [JEV.id]: 0.85, [CLEF.id]: 0.95 } } });
export const clientVectors = async () => {
  const out = [];
  for (const s of scenarios) {
    const def = defs[s.def] as Definition<any, any, any, any>;
    const settled: unknown[] = [];
    const fake = fakeProvider(s.script);
    const client = createClient({ adapters: [fake], now: fixedNow, onSettled: (r) => { settled.push(r); },
      ...(s.deps?.mode === undefined ? {} : { mode: s.deps.mode, decisions: [def] }),
      ...(s.deps?.lock === true ? { locks: [lockFor(def)] } : {}),
      ...(s.deps?.prices === true ? { prices } : {}),
      ...(s.deps?.budget === undefined ? {} : { budget: s.deps.budget }),
      ...(s.deps?.raw === undefined ? {} : { raw: s.deps.raw }),
      ...(s.deps?.deadlineMs === undefined ? {} : { deadlineMs: s.deps.deadlineMs }) });
    const r = await client.decide(def, s.input as never, s.opts ?? {});
    await client.flush();
    const result = r.ok ? { ok: true, value: r.value, envelope: r.envelope, fallback: r.fallback, thresholds: r.thresholds }
      : { ok: false, error: { type: r.error.type, tier: r.error.tier ?? null }, attempts: r.attempts };
    out.push({ ...s, lock: s.deps?.lock === true ? lockFor(def) : null, calls: fake.calls.map((c) => c.tierId),
      expected: JSON.parse(JSON.stringify(result)), settled: JSON.parse(JSON.stringify(settled)) });
  }
  return out;
};

// CLI parity: argv + input files -> exit code, stdout/stderr lines and written files. Module names are logical;
// each port maps them to its own equivalent definitions (Python: tests/conftest.py mirrors, proven by emit hashes).
const cliFile = (name: string) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");
const cliModules = (): Record<string, Record<string, unknown>> => {
  const strict = defineDecision({ ...gate, thresholds: { gate: threshold({ on: "page", objective: { minPrecision: 1.01 } }) } });
  return { defs: { triage, severity }, gate: { gate, notADecision: { hello: "world" } }, strict: { strict }, empty: { notADecision: { hello: "world" } } };
};
const cliInputs = (): Record<string, string> => ({
  "eval.jsonl": cliFile("eval.fit.jsonl"), "fake.json": cliFile("fake.fit.json"), "prices.json": JSON.stringify(prices),
  "registry.json": cliFile("registry.example.json"),
  "bad-registry.json": JSON.stringify({ notice: "EXAMPLE", example: true, providers: [{ provider: "x", namespace: "X", camp: "nope", models: [] }] }),
});
const FIT = ["fit", "gate", "--cases", "eval.jsonl", "--fake", "fake.json", "--lock", "out/urim.lock.json"];
const cliCases: { name: string; argv: string[]; preset?: Record<string, string> }[] = [
  { name: "emit fresh", argv: ["emit", "defs", "--out", "out"] },
  { name: "emit changed", argv: ["emit", "defs", "--out", "out"], preset: { "out/incident-triage_2.0.0.contract.json": "{\n  \"old\": true\n}\n" } },
  { name: "emit module without definitions", argv: ["emit", "empty", "--out", "out"] },
  { name: "emit without --out", argv: ["emit", "defs"] },
  { name: "fit refuses without --yes", argv: [...FIT, "--prices", "prices.json"] },
  { name: "fit refuses, no prices", argv: FIT },
  { name: "fit writes lock", argv: [...FIT, "--prices", "prices.json", "--yes"] },
  { name: "fit report repeat 2", argv: [...FIT, "--prices", "prices.json", "--yes", "--report", "--repeat", "2"] },
  { name: "fit unmet", argv: ["fit", "strict", "--cases", "eval.jsonl", "--fake", "fake.json", "--lock", "l.json", "--yes"] },
  { name: "fit without --fake", argv: ["fit", "gate", "--cases", "eval.jsonl", "--lock", "l.json"] },
  { name: "fit bad repeat", argv: [...FIT, "--repeat", "0"] },
  { name: "fit export not a decision", argv: [...FIT, "--export", "notADecision"] },
  { name: "fit missing --cases", argv: ["fit", "gate", "--lock", "l.json"] },
  { name: "providers", argv: ["providers", "--registry", "registry.json", "--out", "gen/providers.ts"] },
  { name: "providers import override", argv: ["providers", "--registry", "registry.json", "--out", "p.ts", "--import", "urim"] },
  { name: "providers bad registry", argv: ["providers", "--registry", "bad-registry.json", "--out", "p.ts"] },
  { name: "unknown command", argv: ["nope"] },
  { name: "help long", argv: ["--help"] },
  { name: "help short", argv: ["-h"] },
  { name: "help word", argv: ["help"] },
  { name: "help after command", argv: ["fit", "--help"] },
  { name: "no command", argv: [] },
];
export const cliVectors = async () => {
  const modules = cliModules(); const inputs = cliInputs(); const out = [];
  for (const c of cliCases) {
    const files: Record<string, string> = { ...inputs, ...c.preset };
    const stdout: string[] = []; const stderr: string[] = [];
    const io: CliIo = {
      readText: async (p) => { const v = files[p]; if (v === undefined) throw new Error(`ENOENT ${p}`); return v; },
      writeText: async (p, t) => { files[p] = t; }, exists: async (p) => p in files,
      importModule: async (p) => modules[p] ?? {}, out: (l) => stdout.push(l), err: (l) => stderr.push(l),
      now: () => Date.parse("2026-10-28T21:00:00.000Z"),
    };
    const exit = await main(c.argv, io);
    const written = Object.fromEntries(Object.entries(files).filter(([k, v]) => inputs[k] !== v && c.preset?.[k] !== v));
    out.push({ name: c.name, argv: c.argv, preset: c.preset ?? {}, exit, stdout, stderr, written });
  }
  return { inputs, cases: out };
};

// Transport-error rules of the real HTTP adapter (src/adapters/index.ts) + client sendOnce, as port-neutral data.
// Each port reproduces `fault` with its own HTTP stack (mock fetch / httpx.MockTransport / a local socket) and must
// get the same adapter result and the same decide() outcome. No network: every fault is simulated locally.
type Fault = { kind: "reply"; status: number; headers: Record<string, string>; bodyText: string }
  | { kind: "throw"; fault: "connect" | "dns" | "tls" } | { kind: "body_read" } | { kind: "hang" };
const transportCases: { name: string; credential: string | null; fault: Fault; deadlineMs?: number }[] = [
  { name: "200 json", credential: "k", fault: { kind: "reply", status: 200, headers: { "Content-Type": "application/json", "X-Request-Id": "rq-1" }, bodyText: JSON.stringify(triageOk()) } },
  { name: "non-json body", credential: "k", fault: { kind: "reply", status: 200, headers: { "content-type": "text/plain" }, bodyText: "oops" } },
  { name: "empty body", credential: "k", fault: { kind: "reply", status: 200, headers: { "content-type": "application/json" }, bodyText: "" } },
  { name: "401", credential: "k", fault: { kind: "reply", status: 401, headers: { "content-type": "application/json" }, bodyText: "{\"error\":{}}" } },
  { name: "429", credential: "k", fault: { kind: "reply", status: 429, headers: { "content-type": "application/json", "Retry-After": "3" }, bodyText: "{\"error\":{}}" } },
  { name: "500", credential: "k", fault: { kind: "reply", status: 500, headers: { "content-type": "application/json" }, bodyText: "{\"error\":{}}" } },
  { name: "503 non-json", credential: "k", fault: { kind: "reply", status: 503, headers: { "content-type": "application/json" }, bodyText: "<html>down</html>" } },
  { name: "connect refused", credential: "k", fault: { kind: "throw", fault: "connect" } },
  { name: "dns failure", credential: "k", fault: { kind: "throw", fault: "dns" } },
  { name: "tls failure", credential: "k", fault: { kind: "throw", fault: "tls" } },
  { name: "body read failure", credential: "k", fault: { kind: "body_read" } },
  { name: "deadline while hanging", credential: "k", fault: { kind: "hang" }, deadlineMs: 30 },
  { name: "missing credential", credential: null, fault: { kind: "reply", status: 200, headers: { "content-type": "application/json" }, bodyText: "{}" } },
  { name: "empty credential", credential: "", fault: { kind: "reply", status: 200, headers: { "content-type": "application/json" }, bodyText: "{}" } },
];
const faultFetch = (f: Fault, calls: { n: number }): typeof fetch => (async (_url: unknown, init?: RequestInit) => {
  calls.n++;
  if (f.kind === "throw") throw new TypeError("fetch failed", { cause: new Error(f.fault) });
  if (f.kind === "hang") return new Promise<Response>((_, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("aborted"))));
  if (f.kind === "body_read") return new Response(new ReadableStream({ start(c) { c.error(new Error("reset")); } }), { status: 200 });
  return new Response(f.bodyText, { status: f.status, headers: f.headers });
}) as typeof fetch;
const errJson = (e: unknown) => e instanceof UrimError ? { type: e.type, message: e.message, tier: e.tier ?? null } : { threw: true };
export const transportVectors = async () => {
  const constructible = Object.values(DESCRIPTORS).filter((d) => d !== FAKE_SYSTEMONE).map((d) => {
    try { httpAdapter(d); return { provider: d.provider, ok: true, message: null }; } catch (e) { return { provider: d.provider, ok: false, message: (e as Error).message }; }
  });
  const req = encodeRequest(triage, JEV, { report: "x" });
  const out = [];
  for (const c of transportCases) {
    const env = c.credential === null ? {} : { FAKE_SYSTEMONE_API_KEY: c.credential };
    let adapter: unknown = null;
    if (c.fault.kind !== "hang") {
      const calls = { n: 0 };
      try {
        const r = await httpAdapter(FAKE_SYSTEMONE).send(req, { fetch: faultFetch(c.fault, calls), credential: c.credential ?? "", signal: new AbortController().signal });
        adapter = { reply: { status: r.status, headers: r.headers, body: r.body } };
      } catch (e) { adapter = { error: errJson(e) }; }
    }
    const calls = { n: 0 };
    const r = await createClient({ adapters: [httpAdapter(FAKE_SYSTEMONE)], env, fetch: faultFetch(c.fault, calls), now: fixedNow })
      .decide(triage, { report: "x" }, c.deadlineMs === undefined ? {} : { deadlineMs: c.deadlineMs });
    const decide = r.ok ? { ok: true, error: null, attempts: r.envelope.attempts.map((a) => a.outcome) }
      : { ok: false, error: errJson(r.error), attempts: r.attempts.map((a) => a.outcome) };
    out.push({ ...c, deadlineMs: c.deadlineMs ?? null, expected: { adapter, decide, fetchCalls: calls.n } });
  }
  return { constructible, cases: out };
};

const write = (file: string, v: unknown) => writeFileSync(new URL(file, shared), JSON.stringify(v, null, 2) + "\n");
if (process.argv[1]?.endsWith("shared-fixtures.gen.ts")) {
  write("canonical.vectors.json", canonicalVectors());
  write("codec.vectors.json", codecVectors());
  write("lock.vectors.json", lockVectors());
  write("fit.vectors.json", { math: fitMathVectors(), run: await fitRunVectors() });
  write("client.vectors.json", await clientVectors());
  write("cli.vectors.json", await cliVectors());
  write("transport.vectors.json", await transportVectors());
}
