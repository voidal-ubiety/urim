// A (thin) over C: `urim fit` runner. Calls each tier on a labelled eval set through createClient with the
// adapters it is given (fakes only in this slice), then hands scored data to the pure math in fit-math.ts.
import { canonicalize, sha256 } from "./canonical.ts";
import { createClient } from "./client.ts";
import { defineDecision } from "./define.ts";
import { emit } from "./emit.ts";
import { accuracy, brier, fitCutoff, flipRate, percentile, stdev, type CutoffFit, type Scored } from "./fit-math.ts";
import type { Adapter } from "./testing.ts";
import type { Definition, Lock, PriceTable } from "./types.ts";

export type EvalCase = { readonly input: unknown; readonly labels: Readonly<Record<string, string>> };
export type CostEstimate = { readonly perTier: Readonly<Record<string, number>>; readonly total: number | null; readonly currency: string | null; readonly unknown: readonly string[] };
export type TierReport = {
  readonly questions: Readonly<Record<string, { readonly accuracy: number; readonly flipRate: number; readonly brier: number | null }>>;
  readonly accuracyStdev: number;
  readonly latencyMs: { readonly p50: number | null; readonly p95: number | null };
  readonly cost: { readonly amount: number; readonly currency: string } | null;
  readonly cutoffs: Readonly<Record<string, CutoffFit>>;
  readonly failures: number;
};
export type FitReport = { readonly contract: string; readonly n: number; readonly repeat: number; readonly tiers: Readonly<Record<string, TierReport>> };
export type FitOutcome =
  | { readonly status: "needs_confirmation"; readonly estimate: CostEstimate }
  | { readonly status: "ok"; readonly lock: Lock; readonly report: FitReport; readonly estimate: CostEstimate; readonly setHash: string }
  | { readonly status: "objectives_unmet"; readonly unmet: readonly string[]; readonly report: FitReport; readonly estimate: CostEstimate; readonly setHash: string };

const round = (x: number) => Math.round(x * 1e9) / 1e9;

/** C: JSONL eval set -> cases. Each line: {"input": ..., "labels": {question: label}}. */
export const parseCases = (jsonl: string): EvalCase[] => jsonl.split("\n").filter((l) => l.trim() !== "").map((line, i) => {
  const v = JSON.parse(line) as Partial<EvalCase>;
  if (typeof v !== "object" || v === null || !("input" in v) || typeof v.labels !== "object" || v.labels === null) {
    throw new TypeError(`eval line ${i + 1}: needs {input, labels}`);
  }
  return { input: v.input, labels: v.labels };
});

/** C: cases x repeat x per-call price. Unknown prices are listed, never guessed. */
export const estimateFitCost = (def: Definition, n: number, repeat: number, prices: PriceTable | undefined): CostEstimate => {
  const perTier: Record<string, number> = {};
  const unknown: string[] = [];
  let currency: string | null = null;
  for (const t of def.tiers) {
    const e = prices?.entries[t.id];
    if (e?.perCall === undefined) { unknown.push(t.id); continue; } // token-priced rows are unknown before calls
    perTier[t.id] = round(e.perCall * n * repeat);
    currency ??= e.currency;
  }
  const total = unknown.length > 0 ? null : round(Object.values(perTier).reduce((a, b) => a + b, 0));
  return { perTier, total, currency, unknown };
};

export type FitArgs = {
  readonly def: Definition<any, any, any, any>; readonly cases: readonly EvalCase[]; readonly adapters: readonly Adapter[];
  readonly prices?: PriceTable; readonly repeat: number; readonly yes: boolean; readonly now?: () => number;
};

export const runFit = async (args: FitArgs): Promise<FitOutcome> => {
  const def = args.def as Definition;
  const estimate = estimateFitCost(def, args.cases.length, args.repeat, args.prices);
  if (!args.yes) return { status: "needs_confirmation", estimate };
  const now = args.now ?? Date.now;
  const client = createClient({ adapters: args.adapters, ...(args.prices === undefined ? {} : { prices: args.prices }), now });
  const { interpret: _drop, ...bare } = def;
  const tiers: Record<string, TierReport> = {};
  const cuts: Record<string, Record<string, number>> = {};
  const unmet: string[] = [];

  for (const tier of def.tiers) {
    const single = defineDecision({ ...bare, tiers: [tier], failover: { on: [] } });
    // runs[r][i] = answers for case i on run r (or null on failure)
    const runs: { answers: Record<string, { value: string; confidence: number | null }> | null; latency: number; cost: number | null; currency: string | null }[][] = [];
    for (let r = 0; r < args.repeat; r++) {
      const row = [];
      for (const c of args.cases) {
        const res = await client.decide(single, c.input);
        const latency = res.ok ? res.envelope.attempts.reduce((a, x) => a + x.latencyMs, 0) : res.attempts.reduce((a, x) => a + x.latencyMs, 0);
        row.push(res.ok
          ? { answers: res.envelope.answers as Record<string, { value: string; confidence: number | null }>, latency,
              cost: res.envelope.usage.cost?.amount ?? null, currency: res.envelope.usage.cost?.currency ?? null }
          : { answers: null, latency, cost: null, currency: null });
      }
      runs.push(row);
    }
    const scored = (q: string): Scored[] => runs.flatMap((row) => row.map((x, i) => {
      const a = x.answers?.[q];
      return { confidence: a?.confidence ?? null, correct: a !== undefined && a.value === args.cases[i]!.labels[q] };
    }));
    const questions: Record<string, TierReport["questions"][string]> = {};
    for (const q of Object.keys(def.questions)) {
      const xs = scored(q);
      questions[q] = { accuracy: accuracy(xs), brier: brier(xs),
        flipRate: flipRate(runs.map((row) => row.map((x) => x.answers?.[q]?.value ?? "<failed>"))) };
    }
    const cutoffs: Record<string, CutoffFit> = {};
    for (const [name, th] of Object.entries(def.thresholds)) {
      const fit = fitCutoff(scored(th.on), th.objective);
      cutoffs[name] = fit;
      if (!fit.met) unmet.push(`${name}@${tier.id}`);
      if (fit.cutoff !== null) (cuts[name] ??= {})[tier.id] = fit.cutoff;
    }
    const all = runs.flat();
    const perRunAcc = runs.map((row) => {
      const qs = Object.keys(def.questions);
      return accuracy(row.flatMap((x, i) => qs.map((q) => ({ confidence: null, correct: x.answers?.[q]?.value === args.cases[i]!.labels[q] }))));
    });
    tiers[tier.id] = {
      questions, cutoffs, accuracyStdev: round(stdev(perRunAcc)),
      latencyMs: { p50: percentile(all.map((x) => x.latency), 50), p95: percentile(all.map((x) => x.latency), 95) },
      cost: all.every((x) => x.cost !== null) && all[0]?.currency != null
        ? { amount: round(all.reduce((a, x) => a + (x.cost ?? 0), 0)), currency: all[0].currency } : null,
      failures: all.filter((x) => x.answers === null).length,
    };
  }
  const report: FitReport = { contract: def.contract, n: args.cases.length, repeat: args.repeat, tiers };
  const setHash = sha256(canonicalize(args.cases));
  if (unmet.length > 0) return { status: "objectives_unmet", unmet, report, estimate, setHash };
  const lock: Lock = {
    lock: 1, contract: { id: def.contract, hash: emit(def).hash },
    tiers: def.tiers.map((t) => ({ id: t.id, descriptorHash: null })), // TODO(vendor-fact): provider descriptor hash
    cuts,
    eval: { setHash: setHash, n: args.cases.length, repeat: args.repeat, at: new Date(now()).toISOString(), objectivesMet: true },
  };
  return { status: "ok", lock, report, estimate, setHash };
};
