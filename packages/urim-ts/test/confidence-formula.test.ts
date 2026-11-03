// Confidence naming (pre-0.0.1): the definition and every answer name the formula behind `confidence`, and
// providers flagged with the "confidence 0 + empty probabilities = unavailable" sentinel read that as null.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DESCRIPTORS, decodeReply, emit, readEnvelope } from "../src/index.ts";
import * as systemone from "../src/camps/systemone.ts";
import { vendorConfidence } from "../src/camps/shared.ts";
import { escalationAt } from "../src/fit-math.ts";
import { severity, triage, JEV, OPENAI } from "./fixtures.ts";
import { dBody, dPredicate, s1Body, s1Choice, s1Noul } from "./wire.ts";
import { readFileSync } from "node:fs";

const reply = (body: unknown) => ({ status: 200, headers: {}, body, latencyMs: 1 });
const golden = JSON.parse(readFileSync(new URL("./golden/envelope.v1.example.json", import.meta.url), "utf8")) as Record<string, any>;

test("definition confidence names the formula per question type (not top_probability)", () => {
  assert.deepEqual(triage.confidence, { noul: "systemone_normalized", choice: "vendor_unspecified", score: "vendor_unspecified" });
  assert.deepEqual((emit(triage).document as Record<string, unknown>)["confidence"], triage.confidence);
});
test("answers carry confidenceFormula: systemone_normalized for derived yes/no, vendor_unspecified for native", () => {
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.95), team: s1Choice("data", 0.6, { data: 0.8, billing: 0.2 }) })));
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.answers["page"]?.confidence, 0.9);
  assert.equal(r.answers["page"]?.confidenceFormula, "systemone_normalized");
  assert.equal(r.answers["team"]?.confidenceFormula, "vendor_unspecified");
  const o = decodeReply(severity, OPENAI, reply(dBody([dPredicate("page", 0.8)])));
  assert.ok(!o.ok || o.answers["page"]?.confidenceFormula === "systemone_normalized");
});
test("null confidence -> confidenceFormula null", () => {
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.95), team: s1Choice("data", 7, { data: 1 }) })));
  assert.ok(r.ok && r.answers["team"]?.confidenceFormula === null);
});
test("no shipped descriptor sets the unavailable sentinel; a real 0 stays 0", () => {
  for (const d of Object.values(DESCRIPTORS)) assert.equal(d.confidenceUnavailableSentinel, undefined, d.provider);
  const r = decodeReply(triage, JEV, reply(s1Body({ page: s1Noul(0.95), team: s1Choice("data", 0, {}) })));
  assert.ok(r.ok && r.answers["team"]?.confidence === 0 && r.answers["team"]?.confidenceSource === "native");
});
test("sentinel flag: confidence 0 with empty probabilities reads as null (raw kept in native)", () => {
  const s = systemone.decode(triage, JEV, s1Body({ page: s1Noul(0.95), team: s1Choice("data", 0, {}) }), { unavailableSentinel: true });
  assert.ok(s.ok);
  if (!s.ok) return;
  assert.deepEqual([s.answers["team"]?.confidence, s.answers["team"]?.confidenceSource, s.answers["team"]?.confidenceFormula], [null, null, null]);
  assert.equal(s.answers["team"]?.native.confidence, 0);
  assert.equal(s.answers["page"]?.confidence, 0.9); // derived yes/no is untouched
  const kept = systemone.decode(triage, JEV, s1Body({ page: s1Noul(0.95), team: s1Choice("data", 0, { data: 1 }) }), { unavailableSentinel: true });
  assert.ok(kept.ok && kept.answers["team"]?.confidence === 0); // non-empty probabilities: a real 0
  // decisions-shaped probabilities are an array; empty array counts as empty
  assert.equal(vendorConfidence({ confidence: 0, probabilities: [] }, true), null);
  assert.equal(vendorConfidence({ confidence: 0 }, true), 0); // probabilities absent: not the sentinel shape
  assert.equal(vendorConfidence({ confidence: 0, probabilities: [] }, false), 0);
});
test("fit flags sentinel answers: a null confidence never passes a cutoff, even 0", () => {
  assert.equal(escalationAt([{ confidence: null, correct: true }, { confidence: 0, correct: true }], 0), 0.5);
});
test("envelope: confidenceFormula is optional (older urim/1) and closed", () => {
  assert.equal(golden["answers"]["page"]["confidenceFormula"], "systemone_normalized");
  const strip = Object.fromEntries(Object.entries(golden["answers"]).map(([k, v]) => {
    const { confidenceFormula: _d, ...rest } = v as Record<string, unknown>; return [k, rest]; }));
  assert.ok(readEnvelope({ ...golden, answers: strip }).ok);
  assert.ok(!readEnvelope({ ...golden, answers: { ...golden["answers"], page: { ...golden["answers"]["page"], confidenceFormula: "top_probability" } } }).ok);
});
