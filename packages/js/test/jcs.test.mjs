// C-098: the golden RFC 8785 corpus, shared with the Python and Rust ports.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { canonical } from "../dist/jcs.js";
import { Failure, Problem } from "../dist/problem.js";
import { parseDocument } from "../dist/profile.js";

const corpus = JSON.parse(
  readFileSync(new URL("../../../fixtures/jcs/corpus.json", import.meta.url), "utf8"),
).cases;

test("C-098 golden JCS corpus", () => {
  assert.ok(corpus.length >= 30);
  for (const c of corpus) {
    const value = parseDocument(`${c.yaml}\n`);
    if ("jcs" in c) assert.equal(canonical(value), c.jcs, c.name);
    else
      assert.throws(
        () => canonical(value),
        (e) => e instanceof Failure && e.message === Problem.nonFinite,
        c.name,
      );
  }
});
