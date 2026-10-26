// C-096: fixtures/formats.json, the same verdicts as formats.py and formats.rs.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { matches } from "../dist/formats.js";

const table = JSON.parse(
  readFileSync(new URL("../../../fixtures/formats.json", import.meta.url), "utf8"),
).formats;

test("C-096 shared format verdicts", () => {
  assert.equal(Object.keys(table).length, 13);
  for (const [fmt, cases] of Object.entries(table)) {
    for (const c of cases) assert.equal(matches(fmt, c.value), c.ok, `${fmt}: ${JSON.stringify(c.value)}`);
  }
});
