// Hand-checked cases. xs: (0.9,T) (0.8,T) (0.7,F) (0.6,T) (0.5,F)
import { test } from "node:test";
import assert from "node:assert/strict";
import { precisionAt, escalationAt, fitCutoff, accuracy, brier, flipRate, stdev, percentile } from "../src/fit-math.ts";

const xs = [[0.9, true], [0.8, true], [0.7, false], [0.6, true], [0.5, false]].map(([c, k]) => ({ confidence: c as number, correct: k as boolean }));
const close = (a: number | null, b: number) => assert.ok(a !== null && Math.abs(a - b) < 1e-12, `${a} != ${b}`);

test("precision at 0.6 is 3/4", () => close(precisionAt(xs, 0.6), 0.75));
test("precision with nothing kept is null", () => assert.equal(precisionAt(xs, 0.95), null));
test("escalation at 0.7 is 2/5", () => close(escalationAt(xs, 0.7), 0.4));
test("null confidence always escalates", () => close(escalationAt([{ confidence: null, correct: true }, ...xs], 0.5), 1 / 6));

const fits: Array<[string, Parameters<typeof fitCutoff>[1], number | null]> = [
  ["minPrecision 0.75 -> lowest cut meeting it: 0.6", { minPrecision: 0.75 }, 0.6],
  ["minPrecision 1.0 -> 0.8 (2/2)", { minPrecision: 1 }, 0.8],
  ["escalationRate 0.4 -> highest cut within it: 0.7", { escalationRate: 0.4 }, 0.7],
  ["escalationRate 0 -> lowest candidate 0.5", { escalationRate: 0 }, 0.5],
  ["both feasible -> precision cut 0.6", { minPrecision: 0.75, escalationRate: 0.4 }, 0.6],
  ["both infeasible (0.8 > 0.7) -> null", { minPrecision: 1, escalationRate: 0.4 }, null],
  ["unreachable precision -> null", { minPrecision: 1.01 }, null],
];
for (const [name, objective, expected] of fits) {
  test(`fitCutoff: ${name}`, () => assert.equal(fitCutoff(xs, objective).cutoff, expected));
}
test("fitCutoff reports met and achieved precision/escalation", () =>
  assert.deepEqual(fitCutoff(xs, { minPrecision: 0.75 }), { cutoff: 0.6, met: true, precision: 0.75, escalation: 0.2 }));
test("no objective: nothing to fit, trivially met", () =>
  assert.deepEqual(fitCutoff(xs, {}), { cutoff: null, met: true, precision: null, escalation: null }));
test("all-null confidences cannot meet escalation", () =>
  assert.equal(fitCutoff([{ confidence: null, correct: true }], { escalationRate: 0.5 }).met, false));

test("accuracy 3/5", () => close(accuracy(xs), 0.6));
test("brier of (0.9,T),(0.5,F) = (0.01+0.25)/2", () => close(brier([{ confidence: 0.9, correct: true }, { confidence: 0.5, correct: false }]), 0.13));
test("brier ignores null confidence; all null -> null", () => assert.equal(brier([{ confidence: null, correct: true }]), null));
test("flip rate: 1 of 2 cases changed across runs", () => close(flipRate([["a", "b"], ["a", "c"]]), 0.5));
test("flip rate with one run is 0", () => close(flipRate([["a", "b"]]), 0));
test("stdev population of 1,3 = 1", () => close(stdev([1, 3]), 1));
test("p50/p95 nearest-rank", () => { close(percentile([1, 2, 3, 4], 50), 2); close(percentile([1, 2, 3, 4], 95), 4); });
test("percentile of empty is null", () => assert.equal(percentile([], 50), null));
