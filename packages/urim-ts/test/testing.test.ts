import { test } from "node:test";
import assert from "node:assert/strict";
import { fakeProvider, encodeRequest, decodeReply, UrimError } from "../src/index.ts";
import { triage, JEV, CLEF } from "./fixtures.ts";
import { triageOk } from "./wire.ts";

const io = () => ({ signal: new AbortController().signal, fetch: globalThis.fetch, credential: "" });

test("fake fails a step with the scripted UrimError type", async () => {
  const fake = fakeProvider({ [JEV.id]: [{ fail: "timeout" }] });
  await assert.rejects(fake.send(encodeRequest(triage, JEV, { report: "r" }), io()),
    (e: unknown) => e instanceof UrimError && e.type === "timeout" && e.tier === JEV.id);
});
test("fake returns a scripted body that decodes", async () => {
  const fake = fakeProvider({ [CLEF.id]: [{ body: triageOk() }] });
  const r = decodeReply(triage, CLEF, await fake.send(encodeRequest(triage, CLEF, { report: "r" }), io()));
  assert.ok(r.ok);
});
test("fake records the requests it saw", async () => {
  const fake = fakeProvider({ [CLEF.id]: [{ body: {} }] });
  await fake.send(encodeRequest(triage, CLEF, { report: "r" }), io());
  assert.equal(fake.calls.length, 1);
  assert.equal(fake.calls[0]?.tierId, CLEF.id);
});
test("unscripted call is a programming error, not a provider error", async () => {
  const fake = fakeProvider({});
  await assert.rejects(fake.send(encodeRequest(triage, JEV, { report: "r" }), io()),
    (e: unknown) => !(e instanceof UrimError));
});
test("aborted signal rejects with cancelled", async () => {
  const fake = fakeProvider({ [JEV.id]: [{ body: {} }] });
  const ctl = new AbortController(); ctl.abort();
  await assert.rejects(fake.send(encodeRequest(triage, JEV, { report: "r" }), { ...io(), signal: ctl.signal }),
    (e: unknown) => e instanceof UrimError && e.type === "cancelled");
});
