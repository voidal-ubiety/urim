import { test } from "node:test";
import assert from "node:assert/strict";
import { encodeRequest, decodeReply, tier } from "../src/index.ts";
import { triage, severity, JEV, OPENAI } from "./fixtures.ts";
import { s1Body, s1Noul, s1Choice, s1Score, dBody, dPredicate, dScore, dChoice, dRefusal, triageOk } from "./wire.ts";

const input = { report: "db down" };
const reply = (body: unknown, headers: Record<string, string> = {}) => ({ status: 200, headers, body, latencyMs: 5 });
const sevLevels = [{ value: 0, label: "low", probability: 0.1 }, { value: 1, label: "mid", probability: 0.2 }, { value: 2, label: "high", probability: 0.7 }];

// ---- systemone encode (https://docs.typesafe.ai/api/system-one) ----
test("systemone encode: versioned wire model, instructions, noul true/false criteria, choice map", () => {
  const req = encodeRequest(triage, JEV, input);
  assert.deepEqual(req.body, {
    model: "jev-1.14.0", state: input,
    questions: {
      page: { type: "noul", instructions: "Should someone be paged right now?", criteria: { true: "Active impact", false: "No impact" } },
      team: { type: "choice", instructions: "Which team owns this incident?", criteria: { billing: "b", platform: "p", identity: "i", data: "d" } },
    },
  });
});
test("systemone encode: score criteria is an ordered array", () => {
  const req = encodeRequest(severity, JEV, input);
  assert.deepEqual((req.body as { questions: Record<string, unknown> }).questions["sev"],
    { type: "score", instructions: "How severe?", criteria: ["l", "m", "h"] });
});
test("camp follows the body: perplexity posts systemone body to a /v1/decisions URL", () => {
  const pplx = tier({ provider: "perplexity", model: "pplx-decider-latest", version: "v1.2", camp: "systemone", questionTypes: ["noul", "choice"] });
  const req = encodeRequest(triage, pplx, input);
  assert.equal(req.camp, "systemone");
  assert.equal(req.url, "https://api.perplexity.ai/v1/decisions");
  assert.ok("questions" in (req.body as object) && !Array.isArray((req.body as { questions: unknown }).questions));
});
test("cloudflare: body model is clef-flash, URL carries @cf/cloudflare/clef-flash", () => {
  const cf = tier({ provider: "cloudflare", model: "clef-flash", version: "1", camp: "systemone", questionTypes: ["noul", "choice"] });
  const req = encodeRequest(triage, cf, input);
  assert.equal((req.body as { model: string }).model, "clef-flash");
  assert.equal(req.url, "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/clef-flash");
});
test("microsoft: wire model is the deployment name (tier.model)", () => {
  const ms = tier({ provider: "microsoft", model: "my-decision-deploy", version: "1", camp: "systemone", questionTypes: ["noul", "choice"] });
  const req = encodeRequest(triage, ms, input);
  assert.equal((req.body as { model: string }).model, "my-decision-deploy");
  assert.equal(req.url, "{endpoint}/providers/microsoft/v1/systemone");
});
test("fastino: sends fastino/GLiDE", () => {
  const f = tier({ provider: "fastino", model: "GLiDE", version: "1", camp: "systemone", questionTypes: ["noul", "choice"] });
  assert.equal((encodeRequest(triage, f, input).body as { model: string }).model, "fastino/GLiDE");
});

// ---- systemone decode ----
test("systemone noul: label from P(yes), confidence by TypeSafe formula (p_max-1/2)/(1/2)", () => {
  const r = decodeReply(triage, JEV, reply(triageOk()));
  assert.ok(r.ok);
  assert.equal(r.answers["page"]?.value, "yes");
  assert.ok(Math.abs((r.answers["page"]?.confidence ?? 0) - 0.9) < 1e-12);
  assert.deepEqual(r.answers["page"]?.native, { name: "page", value: 0.95, confidence: null });
});
for (const [p, label] of [[0.2, "no"], [0.5, "yes"], [0.51, "yes"]] as const) {
  test(`systemone noul P(yes)=${p} -> ${label}`, () => {
    const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(p), team: s1Choice("data", 0.5, { data: 1 }) })));
    assert.ok(r.ok); assert.equal(r.answers["page"]?.value, label);
  });
}
test("systemone choice keeps native confidence", () => {
  const r = decodeReply(triage, JEV, reply(triageOk(0.4, "billing")));
  assert.ok(r.ok); assert.equal(r.answers["team"]?.value, "billing"); assert.equal(r.answers["team"]?.confidence, 0.4);
});
test("systemone score: label is argmax of probabilities, not the rounded expected index", () => {
  const body = s1Body({ sev: s1Score(1.4, 0.3, { "0": 0.45, "1": 0.1, "2": 0.45000001 }, { "0": "l", "1": "m", "2": "h" }), page: s1Noul(0.1) });
  const r = decodeReply(severity, JEV, reply(body));
  assert.ok(r.ok); assert.equal(r.answers["sev"]?.value, "high"); assert.equal(r.answers["sev"]?.native.value, 1.4);
});
test("systemone choice outside labels is nonconformant", () => {
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.9), team: s1Choice("maybe", 0.9, {}) })));
  assert.ok(!r.ok); assert.equal(r.error.type, "nonconformant_response");
});
test("systemone missing answer is nonconformant", () => {
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.9) })));
  assert.ok(!r.ok); assert.equal(r.error.type, "nonconformant_response");
});
test("systemone usage and answering model are surfaced", () => {
  const r = decodeReply(triage, JEV, reply(triageOk(0.9, "data", "jev-1.14.0")));
  assert.ok(r.ok); assert.deepEqual(r.usage, { inputTokens: 1200, outputTokens: 3 }); assert.equal(r.model, "jev-1.14.0");
});
test("non-object body is nonconformant", () => assert.ok(!decodeReply(triage, JEV, reply("oops")).ok));

// ---- model aliases (descriptor data) ----
test("jev-latest answered by jev-1.14.0 is not a lock violation", () => {
  const latest = tier({ provider: "typesafe", model: "jev-latest", version: "1.14.0", camp: "systemone", questionTypes: ["noul", "choice"] });
  assert.ok(decodeReply(triage, latest, reply(triageOk(0.9, "data", "jev-1.14.0"))).ok);
});
test("fastino answering 'glide' is not a lock violation", () => {
  const f = tier({ provider: "fastino", model: "GLiDE", version: "1", camp: "systemone", questionTypes: ["noul", "choice"] });
  assert.ok(decodeReply(triage, f, reply({ ...triageOk(), model: "glide" })).ok);
});
test("an unexpected answering model is a lock_violation", () => {
  const r = decodeReply(triage, JEV, reply({ ...triageOk(), model: "jev-1.13.0" }));
  assert.ok(!r.ok); assert.equal(r.error.type, "lock_violation");
});

// ---- decisions encode (O2) ----
test("decisions encode: input_json part in a user message, instructions, choices/levels, bare predicate", () => {
  const req = encodeRequest(severity, OPENAI, input);
  assert.equal(req.url, "https://api.openai.com/v1/decisions");
  assert.deepEqual(req.body, {
    model: "gpt-6-luna",
    input: [{ role: "user", content: [{ type: "input_json", data: input }] }],
    questions: [
      { type: "score", name: "sev", instructions: "How severe?",
        levels: [{ label: "low", description: "l" }, { label: "mid", description: "m" }, { label: "high", description: "h" }] },
      { type: "predicate", name: "page", instructions: "Page?" },
    ],
  });
});
test("decisions encode: choice uses choices[{value,description}]", () => {
  const ot = tier({ provider: "openai", model: "gpt-6-luna", version: "0", camp: "decisions", questionTypes: ["noul", "choice"] });
  const q = (encodeRequest(triage, ot, input).body as { questions: Array<Record<string, unknown>> }).questions[1];
  assert.deepEqual(q?.["choices"], [{ value: "billing", description: "b" }, { value: "platform", description: "p" }, { value: "identity", description: "i" }, { value: "data", description: "d" }]);
});

// ---- decisions decode (O3) ----
test("decisions decode: score label from argmax probabilities, predicate from probability", () => {
  const r = decodeReply(severity, OPENAI, reply(dBody([dScore("sev", 1.6, 0.7, sevLevels), dPredicate("page", 0.2)])));
  assert.ok(r.ok);
  assert.equal(r.answers["sev"]?.value, "high"); assert.equal(r.answers["sev"]?.confidence, 0.7);
  assert.equal(r.answers["page"]?.value, "no");
  assert.ok(Math.abs((r.answers["page"]?.confidence ?? 0) - 0.6) < 1e-12);
});
test("decisions decode: null names fall back to question order", () => {
  const r = decodeReply(severity, OPENAI, reply(dBody([dScore(null, 0.2, 0.9, sevLevels.map((l, i) => ({ ...l, probability: i === 0 ? 0.9 : 0.05 }))), dPredicate(null, 0.99)])));
  assert.ok(r.ok); assert.equal(r.answers["sev"]?.value, "low"); assert.equal(r.answers["page"]?.value, "yes");
});
test("decisions decode: boolean choice value never matches a string label", () => {
  const ot = tier({ provider: "openai", model: "gpt-6-luna", version: "0", camp: "decisions", questionTypes: ["noul", "choice"] });
  const r = decodeReply(triage, ot, reply(dBody([dPredicate("page", 0.9), dChoice("team", true, 0.9, [{ value: true, probability: 0.9 }])])));
  assert.ok(!r.ok); assert.equal(r.error.type, "nonconformant_response");
});
test("decisions decode: a per-question refusal maps to the existing `refused` error", () => {
  const r = decodeReply(severity, OPENAI, reply(dBody([dRefusal("sev"), dPredicate("page", 0.9)]), { "x-request-id": "req_123" }));
  assert.ok(!r.ok); assert.equal(r.error.type, "refused"); assert.match(r.error.message, /sev/);
  assert.equal(r.error.requestId, "req_123");
});
test("decisions decode: usage surfaced", () => {
  const r = decodeReply(severity, OPENAI, reply(dBody([dScore("sev", 1, 0.5, sevLevels), dPredicate("page", 0.9)])));
  assert.ok(r.ok); assert.deepEqual(r.usage, { inputTokens: 800, outputTokens: 0 });
});
