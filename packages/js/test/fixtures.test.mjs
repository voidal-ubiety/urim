import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve, dirname } from "node:path";
import { checkFile } from "../dist/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const FIXTURES = resolve(here, "../../../fixtures");
const { cases } = JSON.parse(readFileSync(join(FIXTURES, "cases.json"), "utf8"));
const CLI = resolve(here, "../dist/cli.js");

for (const c of cases) {
  test(`shared case ${c.path}`, () => {
    const path = join(FIXTURES, c.path);
    const r = checkFile(path);
    assert.equal(r.exitCode, c.exit);
    assert.equal(r.line, c.output.replaceAll("{file}", path));
  });
}

test("cli: ok goes to stdout with exit 0, errors to stderr with exit 1", () => {
  const ok = spawnSync(process.execPath, [CLI, "check", join(FIXTURES, "valid/minimal.lock")], { encoding: "utf8" });
  assert.equal(ok.status, 0);
  assert.match(ok.stdout, /ok \(lockfile, hoshen 1, urim 0\.1\)/);
  assert.equal(ok.stderr, "");
  const bad = spawnSync(process.execPath, [CLI, "check", join(FIXTURES, "invalid/hoshen-unsupported.lock")], { encoding: "utf8" });
  assert.equal(bad.status, 1);
  assert.equal(bad.stdout, "");
  assert.match(bad.stderr, /unsupported hoshen version 2/);
});

test("cli: usage and version", () => {
  assert.equal(spawnSync(process.execPath, [CLI], { encoding: "utf8" }).status, 2);
  const v = spawnSync(process.execPath, [CLI, "--version"], { encoding: "utf8" });
  assert.equal(v.status, 0);
  assert.equal(v.stdout.trim(), "urim 0.0.1");
});
