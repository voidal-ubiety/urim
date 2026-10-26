// C-010..C-060: every shared file case, one test per contract ID (fixtures/cases.json).
import assert from "node:assert/strict";
import { join } from "node:path";
import { test } from "node:test";
import { checkFile } from "../dist/index.js";
import { byId, FILE_CASES, FIXTURES } from "./support.mjs";

for (const [id, cases] of byId(FILE_CASES)) {
  test(`${id} shared file cases (${cases.length})`, () => {
    for (const c of cases) {
      const path = join(FIXTURES, c.path);
      const r = checkFile(path);
      assert.equal(r.exitCode, c.exit, `exit for ${c.path}`);
      assert.equal(r.ok, c.exit === 0, `ok for ${c.path}`);
      assert.equal(r.line, c.output.replaceAll("{file}", path), `line for ${c.path}`);
    }
  });
}

test("C-000 every shared case is tagged with a contract ID", () => {
  for (const c of FILE_CASES) assert.match(c.id, /^C-\d{3}$/, c.path);
});
