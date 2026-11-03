import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalize, sha256 } from "../src/index.ts";

test("keys are sorted recursively, no whitespace", () =>
  assert.equal(canonicalize({ b: 1, a: { d: [3, { y: 1, x: 2 }], c: "s" } }), '{"a":{"c":"s","d":[3,{"x":2,"y":1}]},"b":1}'));
test("key insertion order does not change output", () =>
  assert.equal(canonicalize({ a: 1, b: 2 }), canonicalize({ b: 2, a: 1 })));
test("array order is preserved", () => assert.equal(canonicalize([2, 1]), "[2,1]"));
test("undefined members are omitted", () => assert.equal(canonicalize({ a: undefined, b: null }), '{"b":null}'));
for (const bad of [NaN, Infinity, () => 1, Symbol("s"), 1n]) {
  test(`rejects non-JSON value ${String(typeof bad)}`, () => assert.throws(() => canonicalize({ v: bad })));
}
test("sha256 is prefixed hex of the exact string", () =>
  assert.equal(sha256(""), "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
