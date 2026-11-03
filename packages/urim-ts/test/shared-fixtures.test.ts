import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { canonicalVectors, cliVectors, clientVectors, codecVectors, fitMathVectors, fitRunVectors, lockVectors, transportVectors } from "./shared-fixtures.gen.ts";

const read = (f: string) => JSON.parse(readFileSync(new URL(`../../shared-fixtures/${f}`, import.meta.url), "utf8"));

test("shared canonical vectors are current with the TS reference", () => {
  assert.deepEqual(read("canonical.vectors.json"), canonicalVectors());
});

test("shared codec vectors are current with the TS reference", () => {
  assert.deepEqual(read("codec.vectors.json"), JSON.parse(JSON.stringify(codecVectors())));
});

const viaJson = (v: unknown) => JSON.parse(JSON.stringify(v));

test("shared lock, fit and client vectors are current with the TS reference", async () => {
  assert.deepEqual(read("lock.vectors.json"), viaJson(lockVectors()));
  assert.deepEqual(read("fit.vectors.json"), viaJson({ math: fitMathVectors(), run: await fitRunVectors() }));
  assert.deepEqual(read("client.vectors.json"), viaJson(await clientVectors()));
  assert.deepEqual(read("cli.vectors.json"), viaJson(await cliVectors()));
  assert.deepEqual(read("transport.vectors.json"), viaJson(await transportVectors()));
});
