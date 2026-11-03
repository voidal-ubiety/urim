import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { zodSchema } from "../src/zod.ts";

const s = zodSchema(z.object({ report: z.string().max(5), n: z.number().optional() }));

test("valid input parses to the typed value", () => assert.deepEqual(s.parse({ report: "hi" }), { ok: true, value: { report: "hi" } }));
test("invalid input returns issues with dotted paths", () => {
  const r = s.parse({ report: "too long" });
  assert.ok(!r.ok);
  assert.equal(r.issues[0]?.path, "report");
});
test("toJSONSchema uses Zod v4 built-in", () => {
  const js = s.toJSONSchema() as { type: string; required: string[]; properties: { report: { maxLength: number } } };
  assert.equal(js.type, "object");
  assert.deepEqual(js.required, ["report"]);
  assert.equal(js.properties.report.maxLength, 5);
});
