// The README quickstart is the registry page's first example: it must run offline exactly as written.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const readme = readFileSync(new URL("../README.md", import.meta.url), "utf8");

test("README has a JavaScript quickstart that runs offline and prints the answer", () => {
  const block = /```js\n([\s\S]*?)```/.exec(readme)?.[1];
  assert.ok(block !== undefined, "README needs a ```js quickstart block");
  // Inside the package directory so `import "@voidal-ubiety/urim"` resolves by self-reference.
  const file = fileURLToPath(new URL("../.readme-quickstart.tmp.mjs", import.meta.url));
  writeFileSync(file, block);
  try {
    const out = execFileSync(process.execPath, ["--conditions=urim-dev-source", file], { encoding: "utf8", env: {} });
    assert.match(out, /value: 'yes'/);
    assert.match(out, /confidence: 0\.9/);
  } finally {
    rmSync(file, { force: true });
  }
});

test("README has an install line and no internal build notes", () => {
  assert.match(readme, /npm install @voidal-ubiety\/urim@alpha/);
  assert.doesNotMatch(readme, /slice \d|Port of urim/);
});
