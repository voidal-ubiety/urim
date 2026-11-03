// Consumer-driven contract tests for the urim/1 envelope (design §5.2, SemVer note §5.5).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createClient, fakeProvider, readEnvelope } from "../src/index.ts";
import { triage, JEV, prices } from "./fixtures.ts";
import { triageOk } from "./wire.ts";

const golden = JSON.parse(readFileSync(new URL("./golden/envelope.v1.example.json", import.meta.url), "utf8")) as Record<string, unknown>;
const REQUIRED = ["answers", "at", "attempts", "contract", "envelope", "fallback", "requestIds", "thresholds", "tier", "usage"];
const OPTIONAL = ["interpretFailed", "raw"];
const ok = { body: triageOk() };

const live = async () => {
  const r = await createClient({ adapters: [fakeProvider({ [JEV.id]: [ok] })], prices, now: () => Date.parse("2026-10-28T21:00:00.000Z") })
    .decide(triage, { report: "db down" });
  assert.ok(r.ok);
  return JSON.parse(JSON.stringify(r.envelope)) as Record<string, unknown>;
};

test("golden v1 envelope is readable", () => assert.ok(readEnvelope(golden).ok));
test("live envelope matches the golden example exactly", async () => assert.deepEqual(await live(), golden));
test("live envelope top-level keys are the documented set", async () =>
  assert.deepEqual(Object.keys(await live()).filter((k) => !OPTIONAL.includes(k)).sort(), REQUIRED));
test("readers ignore unknown members (additive evolution is a minor change)", () =>
  assert.ok(readEnvelope({ ...golden, new_member: { x: 1 }, tier: { ...(golden["tier"] as object), extra: true } }).ok));
for (const key of REQUIRED) {
  test(`removing required member ${key} breaks the reader (would be a major change)`, () => {
    const { [key]: _gone, ...rest } = golden;
    assert.ok(!readEnvelope(rest).ok);
  });
}
test("unknown major version is rejected", () => assert.ok(!readEnvelope({ ...golden, envelope: "urim/2" }).ok));
test("portable confidence must be number or null", () => {
  const answers = { page: { ...(golden["answers"] as Record<string, object>)["page"], confidence: "high" } };
  assert.ok(!readEnvelope({ ...golden, answers }).ok);
});
