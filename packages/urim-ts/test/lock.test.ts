import { test } from "node:test";
import assert from "node:assert/strict";
import { parseLock, serializeLock, UrimError } from "../src/index.ts";
import type { Lock } from "../src/index.ts";

const H = `sha256:${"a".repeat(64)}`;
const full: Lock = {
  lock: 1, contract: { id: "c@1.0.0", hash: H },
  tiers: [{ id: "typesafe/jev@1.14.0", descriptorHash: null }],
  cuts: { gate: { "typesafe/jev@1.14.0": 0.6 } },
  eval: { setHash: H, n: 5, repeat: 2, at: "2026-10-28T21:00:00.000Z", objectivesMet: true },
};

test("round trip: serialize then parse is identity", () => {
  const r = parseLock(JSON.parse(serializeLock(full)));
  assert.ok(r.ok);
  assert.deepEqual(r.lock, full);
});
test("serialization is stable (sorted keys, trailing newline)", () => {
  const text = serializeLock(full);
  assert.ok(text.endsWith("\n"));
  assert.equal(text, serializeLock(JSON.parse(text) as Lock));
  assert.ok(text.indexOf('"contract"') < text.indexOf('"cuts"'));
});
test("readers ignore unknown keys", () => {
  const r = parseLock({ ...full, futureField: 1 });
  assert.ok(r.ok && !("futureField" in r.lock));
});
const bad: Array<[string, unknown]> = [
  ["wrong format version", { ...full, lock: 2 }],
  ["hash without sha256 prefix", { ...full, contract: { id: "c", hash: "abc" } }],
  ["cut outside 0..1", { ...full, cuts: { gate: { t: 1.5 } } }],
  ["cut not a number", { ...full, cuts: { gate: { t: "0.5" } } }],
  ["tiers not an array", { ...full, tiers: {} }],
  ["eval.n negative", { ...full, eval: { ...full.eval, n: -1 } }],
  ["not an object", "lock"],
];
for (const [name, value] of bad) {
  test(`rejects ${name}`, () => assert.ok(!parseLock(value).ok));
}
test("writer is strict: serializing an invalid lock throws lock_violation", () =>
  assert.throws(() => serializeLock({ ...full, cuts: { g: { t: 2 } } }), (e: unknown) => e instanceof UrimError && e.type === "lock_violation"));
test("minimal lock (contract + cuts) is valid", () => assert.ok(parseLock({ lock: 1, contract: { id: "c", hash: H }, cuts: {} }).ok));
