import { test } from "node:test";
import assert from "node:assert/strict";
import { UrimError, classifyReply } from "../src/index.ts";

test("UrimError is frozen and keeps its cause", () => {
  const cause = new Error("socket");
  const e = new UrimError("timeout", "tier timed out", { cause, tier: "a/b@1" });
  assert.equal(e.cause, cause);
  assert.ok(Object.isFrozen(e));
  assert.equal(e.retryable, true);
});
test("invalid_input is not retryable", () => assert.equal(new UrimError("invalid_input", "x").retryable, false));

const cases: Array<[number, string | null]> = [
  [200, null], [400, "invalid_request"], [401, "auth"], [403, "auth"], [404, "invalid_request"],
  [408, "timeout"], [413, "invalid_request"], [422, "invalid_request"], [429, "rate_limited"],
  [500, "provider_unavailable"], [502, "provider_unavailable"], [503, "provider_unavailable"], [504, "timeout"],
  [418, "invalid_request"],
];
for (const [status, expected] of cases) {
  test(`generic classification: HTTP ${status} -> ${expected}`, () =>
    assert.equal(classifyReply({ status, headers: {}, body: {}, latencyMs: 1 }), expected));
}
