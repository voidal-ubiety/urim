// Release metadata: the npm name is `@voidal-ubiety/urim` and the public entry points resolve by that name (self-reference).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as Record<string, unknown>;

test("package name is `@voidal-ubiety/urim`", () => {
  assert.equal(pkg.name, "@voidal-ubiety/urim");
});

test("`@voidal-ubiety/urim` and `@voidal-ubiety/urim/adapters` resolve by package name", async () => {
  const core = (await import("@voidal-ubiety/urim")) as Record<string, unknown>;
  const adapters = (await import("@voidal-ubiety/urim/adapters")) as Record<string, unknown>;
  assert.equal(typeof core.createClient, "function");
  const factories = Object.keys(adapters).filter((k) => k !== "httpAdapter");
  assert.ok(factories.length >= 2 && factories.includes("openaiDecisions"));
  for (const k of factories) assert.equal(typeof adapters[k], "function", k);
});

test("release metadata: 0.0.1-alpha.1, publishable, Apache-2.0, repository", () => {
  assert.equal(pkg.version, "0.0.1-alpha.1");
  assert.equal(pkg.private, undefined);
  assert.equal(pkg.license, "Apache-2.0");
  assert.deepEqual(pkg.repository, { type: "git", url: "git+https://github.com/voidal-ubiety/urim.git", directory: "packages/urim-ts" });
});

test("published entry points are built JS + .d.ts under dist/; source only under the private `urim-dev-source` condition (a generic `source` condition would resolve to unshipped files for consumers)", () => {
  const exp = pkg.exports as Record<string, Record<string, string>>;
  for (const [sub, file] of [[".", "index"], ["./zod", "zod"], ["./testing", "testing"], ["./adapters", "adapters/index"]] as const) {
    assert.deepEqual(exp[sub], { "urim-dev-source": `./src/${file}.ts`, types: `./dist/src/${file}.d.ts`, default: `./dist/src/${file}.js` });
  }
  assert.deepEqual(pkg.bin, { urim: "dist/bin/urim.js" });
  assert.deepEqual(pkg.files, ["dist", "LICENSE", "NOTICE"]);
});

test("LICENSE and NOTICE match the repository root", () => {
  for (const f of ["LICENSE", "NOTICE"]) {
    assert.equal(readFileSync(new URL(`../${f}`, import.meta.url), "utf8"), readFileSync(new URL(`../../../${f}`, import.meta.url), "utf8"));
  }
});

test("registry links and keywords", () => {
  assert.deepEqual(pkg.bugs, { url: "https://github.com/voidal-ubiety/urim/issues" });
  assert.equal(pkg.homepage, "https://urim.sh");
  assert.ok((pkg.keywords as string[]).includes("llm"));
});
