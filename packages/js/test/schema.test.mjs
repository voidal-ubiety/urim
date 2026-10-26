// C-096 bounds: an open upper bound. Today's schema has none ((0, 1] is open below only), so the
// generator's `maxOpen: true` is pinned here with a synthetic node instead of a fixture.
import assert from "node:assert/strict";
import { test } from "node:test";
import { Failure } from "../dist/problem.js";
import { validate } from "../dist/schema.js";

test("C-096 a number in [0, 1) refuses 1 and accepts 0.5", () => {
  const node = { k: "num", min: 0, max: 1, minOpen: false, maxOpen: true, desc: "a number in [0, 1)" };
  validate(node, 0.5);
  validate(node, 0n);
  assert.throws(
    () => validate(node, 1),
    (e) => e instanceof Failure && e.message.endsWith("must be a number in [0, 1)"),
  );
});
