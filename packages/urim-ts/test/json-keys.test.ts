// Rule (2026-10-29): every JSON key Urim itself writes is camelCase. Map keys chosen by the user (question,
// threshold and tier names) and vendor data (native, raw) are not Urim's keys and are skipped.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emit } from "../src/emit.ts";
import { triage, severity } from "./fixtures.ts";

const MAPS = new Set(["questions", "thresholds", "answers", "requestIds", "perTier", "cutoffs", "properties", "labels"]);
const OPAQUE = new Set(["cuts", "native", "raw", "input", "script", "body"]);
const CAMEL = /^[a-z][a-zA-Z0-9]*$/;

export const snakeKeys = (v: unknown, path = "$", out: string[] = []): string[] => {
  if (Array.isArray(v)) v.forEach((x, i) => snakeKeys(x, `${path}[${i}]`, out));
  else if (typeof v === "object" && v !== null) {
    for (const [k, x] of Object.entries(v)) {
      if (OPAQUE.has(k)) continue;
      if (!CAMEL.test(k)) out.push(`${path}.${k}`);
      if (MAPS.has(k) || (k === "tiers" && !Array.isArray(x))) {
        for (const [mk, mx] of Object.entries(x as object)) snakeKeys(mx, `${path}.${k}.${mk}`, out);
      } else snakeKeys(x, `${path}.${k}`, out);
    }
  }
  return out;
};

const read = (rel: string) => JSON.parse(readFileSync(new URL(rel, import.meta.url), "utf8"));

test("emitted contracts use camelCase keys only", () => {
  for (const d of [triage, severity]) assert.deepEqual(snakeKeys(emit(d).document), []);
});

test("golden envelope and shared output vectors use camelCase keys only", () => {
  assert.deepEqual(snakeKeys(read("./golden/envelope.v1.example.json")), []);
  const client = read("../../shared-fixtures/client.vectors.json") as { expected: unknown; settled: unknown; lock: unknown }[];
  assert.deepEqual(client.flatMap((v) => snakeKeys([v.expected, v.settled, v.lock])), []);
  const fit = read("../../shared-fixtures/fit.vectors.json") as { run: { runs: { expected: unknown }[]; estimate: unknown } };
  assert.deepEqual(snakeKeys([fit.run.estimate, ...fit.run.runs.map((r) => r.expected)]), []);
  const lock = read("../../shared-fixtures/lock.vectors.json") as { input: unknown }[];
  assert.deepEqual(lock.flatMap((v) => snakeKeys(v.input)), []);
});
