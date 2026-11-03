// Slice 4b fix 2: every portable confidence says who computed it (native = the vendor returned it; urim_derived = Urim did).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { decodeReply, readEnvelope } from "../src/index.ts";
import { severity, triage, JEV, OPENAI } from "./fixtures.ts";
import { dBody, dPredicate, dScore, s1Body, s1Choice, s1Noul } from "./wire.ts";

const reply = (body: unknown) => ({ status: 200, headers: {}, body, latencyMs: 1 });
const golden = JSON.parse(readFileSync(new URL("./golden/envelope.v1.example.json", import.meta.url), "utf8")) as Record<string, any>;

test("OpenAI predicate confidence is urim_derived; OpenAI score confidence is native", () => {
  const r = decodeReply(severity, OPENAI, reply(dBody([
    dScore("sev", 2, 0.7, [{ value: 0, label: "low", probability: 0.1 }, { value: 1, label: "mid", probability: 0.2 }, { value: 2, label: "high", probability: 0.7 }]),
    dPredicate("page", 0.8)])));
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.answers["page"]?.confidenceSource, "urim_derived");
  assert.equal(r.answers["page"]?.native.confidence, null);
  assert.equal(r.answers["sev"]?.confidenceSource, "native");
});
test("systemone noul is urim_derived (normalized formula, computed client-side); choice is native", () => {
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.95), team: s1Choice("data", 0.6, { data: 0.8, billing: 0.2 }) })));
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.answers["page"]?.confidenceSource, "urim_derived");
  assert.equal(r.answers["team"]?.confidenceSource, "native");
});
test("no confidence -> confidenceSource null", () => {
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.95), team: s1Choice("data", 7, { data: 1 }) })));
  assert.ok(r.ok && r.answers["team"]?.confidence === null && r.answers["team"]?.confidenceSource === null);
});
test("golden envelope carries confidenceSource on every answer", () => {
  assert.equal(golden["answers"]["page"]["confidenceSource"], "urim_derived");
  assert.equal(golden["answers"]["team"]["confidenceSource"], "native");
});
test("readEnvelope: older urim/1 envelopes without confidenceSource still read (additive, minor)", () => {
  const answers = Object.fromEntries(Object.entries(golden["answers"]).map(([k, v]) => {
    const { confidenceSource: _drop, ...rest } = v as Record<string, unknown>; return [k, rest];
  }));
  assert.ok(readEnvelope({ ...golden, answers }).ok);
});
test("readEnvelope rejects an unknown confidenceSource value", () => {
  const answers = { ...golden["answers"], page: { ...golden["answers"]["page"], confidenceSource: "guessed" } };
  assert.ok(!readEnvelope({ ...golden, answers }).ok);
});
