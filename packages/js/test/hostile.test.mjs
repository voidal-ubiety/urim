// C-085, C-091: in-process guarantees behind the hostile-input suite (scripts/hostile.py).
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";
import * as urim from "../dist/index.js";
import { parseDocument } from "../dist/profile.js";

const fixture = (name) => readFileSync(new URL(`../../../fixtures/hostile/${name}`, import.meta.url), "utf8");
// The file the gadget fixtures try to create; one source, shared with scripts/hostile.py.
const CANARY = JSON.parse(
  readFileSync(new URL("../../../fixtures/hostile.json", import.meta.url), "utf8"),
).canary;

test("C-091 __proto__/constructor/prototype keys never touch Object.prototype", () => {
  const before = Object.getOwnPropertyNames(Object.prototype).sort();
  const text = fixture("proto-pollution-nested.lock");
  assert.equal(urim.checkText("p.lock", text).line, "p.lock: ok (lockfile, hoshen 1, urim x)");
  const value = parseDocument(text);
  assert.deepEqual(Object.getOwnPropertyNames(Object.prototype).sort(), before);
  assert.equal({}.polluted, undefined);
  assert.equal({}.isAdmin, undefined);
  // Mapping keys live only in a Map, never as object properties, so "__proto__" is an
  // ordinary key and no assignment to a prototype can happen.
  assert.deepEqual(Object.keys(value), ["strings", "size"]);
  assert.ok(value.strings instanceof Map);
  assert.deepEqual(
    [...value.strings.keys()],
    ["hoshen", "urim", "__proto__", "constructor", "prototype", "q"],
  );
  assert.equal(value.strings.get("hoshen"), 1n); // the smuggled `hoshen: 2` stayed nested
});

test("C-085 deserialization-gadget tags are rejected and nothing executes", () => {
  for (const name of [
    "gadget-js-function.lock",
    "gadget-js-undefined-regexp.lock",
    "gadget-python-object-apply.lock",
    "gadget-python-name.lock",
    "gadget-python-object-new.lock",
    "gadget-ruby-object.lock",
  ]) {
    assert.equal(urim.checkText(name, fixture(name)).line, `${name}: error: tags are not allowed`);
  }
  assert.equal(existsSync(CANARY), false);
});
