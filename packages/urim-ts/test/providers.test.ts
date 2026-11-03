import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { generateProviders, parseRegistry } from "../src/providers.ts";
import { FakeSystemOne, Cloudflare, OpenAI } from "../src/providers.generated.ts";
import { JEV, CLEF, OPENAI } from "./fixtures.ts";

const registryText = readFileSync(new URL("./fixtures/registry.example.json", import.meta.url), "utf8");
const registry = parseRegistry(JSON.parse(registryText));

test("checked-in providers.generated.ts is up to date with the example registry", () =>
  assert.equal(readFileSync(new URL("../src/providers.generated.ts", import.meta.url), "utf8"),
    generateProviders(registry, { source: "test/fixtures/registry.example.json" })));
test("constant names follow Namespace.Model_version", () => {
  assert.deepEqual(FakeSystemOne.Jev_1_14_0, JEV);
  assert.deepEqual(Cloudflare.ClefFlash_x_y_z, CLEF);
  assert.deepEqual(OpenAI.Gpt6Luna_0_0_0, OPENAI);
});
test("generated namespaces are frozen", () => assert.ok(Object.isFrozen(FakeSystemOne)));
test("generated source carries the example-data notice", () =>
  assert.match(generateProviders(registry, { source: "x" }), /EXAMPLE DATA ONLY/));
test("registry with a bad camp is rejected", () =>
  assert.throws(() => parseRegistry({ notice: "n", example: true, providers: [{ provider: "p", namespace: "P", camp: "nope", models: [] }] })));
test("registry with a duplicate constant name is rejected", () =>
  assert.throws(() => parseRegistry({ notice: "n", example: true, providers: [{ provider: "p", namespace: "P", camp: "systemone",
    models: [{ model: "a", version: "1.0", questionTypes: ["noul"] }, { model: "a", version: "1.0", questionTypes: ["noul"] }] }] })));
