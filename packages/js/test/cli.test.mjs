// C-001..C-007, C-012: the `urim` command line (fixtures/cli.json plus JS-specific checks).
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { byId, CLI, CLI_CASES, PACKAGE_ROOT, runCli } from "./support.mjs";

for (const [id, cases] of byId(CLI_CASES)) {
  test(`${id} shared CLI cases (${cases.length})`, () => {
    for (const c of cases) {
      assert.deepEqual(
        runCli(c.args),
        { exit: c.exit, stdout: c.stdout, stderr: c.stderr },
        JSON.stringify(c.args),
      );
    }
  });
}

test("C-007 package bin entry point is dist/cli.js with a node shebang", () => {
  const pkg = JSON.parse(readFileSync(join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.deepEqual(pkg.bin, { urim: "dist/cli.js" });
  assert.equal(readFileSync(CLI, "utf8").split("\n", 1)[0], "#!/usr/bin/env node");
});

test("C-012 unreadable file (permission denied) reports cannot read file", {
  skip: process.getuid?.() === 0 && "root ignores file modes",
}, () => {
  const dir = mkdtempSync(join(tmpdir(), "urim-"));
  try {
    const path = join(dir, "locked.lock");
    writeFileSync(path, 'hoshen: 2\nurim: "0.1"\n');
    chmodSync(path, 0o000);
    assert.deepEqual(runCli(["check", path]), {
      exit: 1,
      stdout: "",
      stderr: `${path}: error: cannot read file\n`,
    });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("D-012 non-UTF-8 path bytes in argv are lost by Node (cannot read file)", {
  skip: process.platform === "win32" && "POSIX byte paths only",
}, () => {
  const dir = mkdtempSync(join(tmpdir(), "urim-"));
  try {
    const r = spawnSync(
      "sh",
      [
        "-c",
        `f=$(printf 'f\\377.lock'); printf 'hoshen: 2\\nurim: x\\n' > "$f"; exec "$0" "$1" check "$f"`,
        process.execPath,
        CLI,
      ],
      { cwd: dir },
    );
    assert.equal(r.status, 1);
    assert.match(r.stderr.toString(), /: error: cannot read file\n$/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
