// Release metadata: the npm name is `urim` and the public entry points resolve by that name (self-reference).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as Record<string, unknown>;

test("package name is `urim`", () => {
  assert.equal(pkg.name, "urim");
});

test("`urim` and `urim/adapters` resolve by package name", async () => {
  const core = (await import("urim")) as Record<string, unknown>;
  const adapters = (await import("urim/adapters")) as Record<string, unknown>;
  assert.equal(typeof core.createClient, "function");
  assert.equal(typeof adapters.typesafeJev, "function");
  assert.equal(typeof adapters.openaiDecisions, "function");
});

test("release metadata: 0.0.1, publishable, Apache-2.0, repository", () => {
  assert.equal(pkg.version, "0.0.1");
  assert.equal(pkg.private, undefined);
  assert.equal(pkg.license, "Apache-2.0");
  assert.deepEqual(pkg.repository, { type: "git", url: "git+https://github.com/voidal-ubiety/urim.git", directory: "packages/urim-ts" });
});

test("published entry points are built JS + .d.ts under dist/; source only under the `source` condition", () => {
  const exp = pkg.exports as Record<string, Record<string, string>>;
  for (const [sub, file] of [[".", "index"], ["./zod", "zod"], ["./testing", "testing"], ["./adapters", "adapters/index"]] as const) {
    assert.deepEqual(exp[sub], { source: `./src/${file}.ts`, types: `./dist/src/${file}.d.ts`, default: `./dist/src/${file}.js` });
  }
  assert.deepEqual(pkg.bin, { urim: "dist/bin/urim.js" });
  assert.deepEqual(pkg.files, ["dist", "LICENSE", "NOTICE"]);
});

test("LICENSE and NOTICE match the repository root", () => {
  for (const f of ["LICENSE", "NOTICE"]) {
    assert.equal(readFileSync(new URL(`../${f}`, import.meta.url), "utf8"), readFileSync(new URL(`../../../${f}`, import.meta.url), "utf8"));
  }
});
