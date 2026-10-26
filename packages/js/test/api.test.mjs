// C-070..C-072: the library API exported from the package root.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import * as urim from "../dist/index.js";
import { PACKAGE_ROOT } from "./support.mjs";

test("C-070 checkText validates text; the file name is only used in the message", () => {
  const r = urim.checkText(
    "no/such/file.lock",
    'hoshen: 2\nurim: "0.2"\ngenerated_at: "2026-10-26T10:00:00-04:00"\ncompiler: {name: urim, version: 0.2.0}\nintegrity: "sha256-RQmDCUPMRsURYEALq1dPcacebjwTGbE8W7juQwUmLzU="\ncontracts: {}\n',
  );
  assert.deepEqual(r, {
    ok: true,
    line: "no/such/file.lock: ok (lockfile, hoshen 2, urim 0.2)",
    exitCode: 0,
  });
  assert.equal(
    urim.checkText(
      "",
      '\uFEFFhoshen: 2\nurim: "0.2"\ngenerated_at: "2026-10-26T10:00:00-04:00"\ncompiler: {name: urim, version: 0.2.0}\nintegrity: "sha256-RQmDCUPMRsURYEALq1dPcacebjwTGbE8W7juQwUmLzU="\ncontracts: {}\n',
    ).line,
    ": ok (lockfile, hoshen 2, urim 0.2)",
  );
});

test("C-071 a result carries ok, the exact line, and exit code 0 or 1", () => {
  assert.deepEqual(urim.checkText("f", "[]"), {
    ok: false,
    line: "f: error: root must be a mapping",
    exitCode: 1,
  });
  assert.deepEqual(urim.checkFile(join("definitely", "missing")), {
    ok: false,
    line: `${join("definitely", "missing")}: error: cannot read file`,
    exitCode: 1,
  });
});

test("C-072 SUPPORTED_HOSHEN is [2] and VERSION matches package.json", () => {
  assert.deepEqual([...urim.SUPPORTED_HOSHEN], [2n]);
  const pkg = JSON.parse(readFileSync(join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(urim.VERSION, pkg.version);
});
