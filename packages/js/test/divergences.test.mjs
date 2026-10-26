// D-008, D-009, D-011, D-013, D-014: pinned JS behavior for known cross-language divergences (fixtures/divergences.json).
import assert from "node:assert/strict";
import { join } from "node:path";
import { test } from "node:test";
import { checkFile } from "../dist/index.js";
import { byId, DIVERGENCES, FIXTURES } from "./support.mjs";

for (const [id, cases] of byId(DIVERGENCES)) {
  test(`${id} pinned JS behavior (${cases.length})`, () => {
    for (const c of cases) {
      const path = join(FIXTURES, c.path);
      const r = checkFile(path);
      assert.equal(r.exitCode, c.expect.js.exit, c.path);
      assert.equal(r.line, c.expect.js.output.replaceAll("{file}", path), c.path);
    }
  });
}
