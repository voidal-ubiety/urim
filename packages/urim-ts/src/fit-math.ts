// C: pure fitting math for `urim fit` (design §6, D8). No I/O; every function is hand-checked in test/fit-math.test.ts.
import type { Objective } from "./types.ts";

/** One scored prediction on the threshold's question: portable confidence and whether value == label. */
export type Scored = { readonly confidence: number | null; readonly correct: boolean };
export type CutoffFit = { readonly cutoff: number | null; readonly met: boolean; readonly precision: number | null; readonly escalation: number | null };

const kept = (xs: readonly Scored[], c: number) => xs.filter((x) => x.confidence !== null && x.confidence >= c);

/** Precision of answers that pass cutoff c; null when nothing passes. */
export const precisionAt = (xs: readonly Scored[], c: number): number | null => {
  const k = kept(xs, c);
  return k.length === 0 ? null : k.filter((x) => x.correct).length / k.length;
};
/** Fraction escalated (below c, or no portable confidence). */
export const escalationAt = (xs: readonly Scored[], c: number): number =>
  xs.length === 0 ? 0 : (xs.length - kept(xs, c).length) / xs.length;

const candidates = (xs: readonly Scored[]): number[] =>
  [...new Set(xs.flatMap((x) => (x.confidence === null ? [] : [x.confidence])))].sort((a, b) => a - b);

/**
 * Candidate cutoffs are the observed confidences.
 * minPrecision p: lowest cutoff whose precision >= p (most coverage that meets p).
 * escalationRate r: highest cutoff whose escalation <= r (most precision within the escalation budget).
 * Both: precision cut, if it does not exceed the escalation cut; else unmet.
 */
export const fitCutoff = (xs: readonly Scored[], objective: Objective): CutoffFit => {
  const { minPrecision: p, escalationRate: r } = objective;
  if (p === undefined && r === undefined) return { cutoff: null, met: true, precision: null, escalation: null };
  const cs = candidates(xs);
  const cP = p === undefined ? undefined : cs.find((c) => (precisionAt(xs, c) ?? -1) >= p) ?? null;
  const cE = r === undefined ? undefined : [...cs].reverse().find((c) => escalationAt(xs, c) <= r) ?? null;
  const cutoff = cP === null || cE === null ? null
    : cP !== undefined && cE !== undefined ? (cP <= cE ? cP : null)
    : (cP ?? cE ?? null);
  return cutoff === null ? { cutoff: null, met: false, precision: null, escalation: null }
    : { cutoff, met: true, precision: precisionAt(xs, cutoff), escalation: escalationAt(xs, cutoff) };
};

export const accuracy = (xs: readonly Scored[]): number => (xs.length === 0 ? 0 : xs.filter((x) => x.correct).length / xs.length);

/** Brier score treating portable confidence as P(correct). Ignores null confidence; null when none. */
export const brier = (xs: readonly Scored[]): number | null => {
  const s = xs.filter((x): x is { confidence: number; correct: boolean } => x.confidence !== null);
  return s.length === 0 ? null : s.reduce((a, x) => a + (x.confidence - (x.correct ? 1 : 0)) ** 2, 0) / s.length;
};

/** runs[r][i] = answer for case i on run r. Fraction of cases whose answer changed between runs. */
export const flipRate = (runs: readonly (readonly string[])[]): number => {
  const n = runs[0]?.length ?? 0;
  if (n === 0) return 0;
  let flips = 0;
  for (let i = 0; i < n; i++) if (new Set(runs.map((r) => r[i])).size > 1) flips++;
  return flips / n;
};

export const stdev = (xs: readonly number[]): number => {
  if (xs.length === 0) return 0;
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / xs.length);
};

/** Nearest-rank percentile. */
export const percentile = (xs: readonly number[], p: number): number | null => {
  if (xs.length === 0) return null;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, Math.ceil((p / 100) * s.length) - 1))] ?? null;
};
