// C: plan-then-execute. The plan is data; the loop (slice 2) only carries it out.
import { FAILOVER_TYPES, type ErrorType } from "./errors.ts";
import { deepFreeze } from "./freeze.ts";
import { encodeRequest } from "./camps/index.ts";
import type { Budget, Definition, Plan, PlanStep, PriceTable, Tier, WireRequest } from "./types.ts";

export type PlanOptions = {
  readonly budget?: Budget; readonly prices?: PriceTable;
  /** The prepared input. Needed only for the pre-call token estimate; without it token-priced rows are unknown. */
  readonly input?: unknown;
};

/** Pre-call input-token estimate: the UTF-8 byte length of the encoded JSON body.
 *  Rationale: in byte-level BPE tokenizers every token covers >= 1 byte, so bytes >= tokens for the body text.
 *  UNVERIFIED for these vendors: their tokenizers are undocumented and any server-side prompt overhead is unknown,
 *  so this is a conservative heuristic (expected to over-estimate), not a guaranteed bound. Pure, no I/O. */
export const estimateInputTokens = (req: WireRequest): number =>
  new TextEncoder().encode(JSON.stringify(req.body)).length;

type Estimate = Pick<PlanStep, "estimatedCost" | "costSource" | "estimatedInputTokens">;
const UNKNOWN: Estimate = { estimatedCost: null, costSource: null };

/** Flat perCall wins; else tokens-from-request x dated price; else unknown (never skipped, D5). Never uses a reply. */
const estimateCost = (def: Definition, tier: Tier, opts: PlanOptions): Estimate => {
  const entry = opts.prices?.entries[tier.id];
  if (entry === undefined) return UNKNOWN;
  if (opts.budget !== undefined && entry.currency !== opts.budget.currency) return UNKNOWN;
  if (entry.perCall !== undefined) return { estimatedCost: entry.perCall, costSource: "per_call" };
  if (entry.perMInputTokens == null || opts.input === undefined) return UNKNOWN;
  const tokens = estimateInputTokens(encodeRequest(def, tier, opts.input));
  return { estimatedCost: (tokens * entry.perMInputTokens) / 1_000_000, costSource: "estimated_pre_call", estimatedInputTokens: tokens };
};

const planStep = (def: Definition, tier: Tier, opts: PlanOptions, budgetApplies: boolean): PlanStep => {
  const est = estimateCost(def, tier, opts);
  const over = budgetApplies && est.estimatedCost !== null && est.estimatedCost > (opts.budget?.maxCost ?? Infinity);
  return over ? { tier, action: "skip", reason: "budget", ...est, estimatedCost: est.estimatedCost as number } : { tier, action: "call", ...est };
};

export const planAttempts = (def: Definition, opts: PlanOptions = {}): Plan => {
  const budgetApplies = opts.budget !== undefined && def.failover.on.includes("budget");
  return deepFreeze({ contract: def.contract, steps: def.tiers.map((t) => planStep(def, t, opts, budgetApplies)) });
};

/** Public name: what would `decide` try, in which order, and what would it skip. Pure, no I/O. */
export const explain = planAttempts;

/** After a failed attempt: move on, or abstain. */
export const nextStep = (def: Definition, failure: ErrorType): "next" | "abstain" =>
  FAILOVER_TYPES.has(failure) && def.failover.on.includes(failure) ? "next" : "abstain";
