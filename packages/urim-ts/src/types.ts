// D: plain data shapes. No behaviour lives here.
import type { ErrorType, Issue } from "./errors.ts";

export type Camp = "systemone" | "decisions";
export type QuestionType = "noul" | "choice" | "score";

export type Tier = {
  readonly id: string; readonly provider: string; readonly model: string; readonly version: string;
  readonly camp: Camp; readonly questionTypes: readonly QuestionType[];
};

export type Question<L extends string = string> = {
  readonly type: QuestionType; readonly prompt: string; readonly options: Readonly<Record<L, string>>;
};
export type Questions = Readonly<Record<string, Question>>;

export type Objective = Readonly<{ minPrecision?: number; escalationRate?: number }>;
export type Threshold = { readonly on: string; readonly default: number | null; readonly objective: Objective };

/** Internal schema barrier (D9): Zod is adapted to this later; nothing else in the core sees Zod. */
export type SchemaAdapter<I> = {
  parse(value: unknown): { ok: true; value: I } | { ok: false; issues: readonly Issue[] };
  toJSONSchema(): unknown;
};

export type Thresholds = Readonly<Record<string, Threshold>>;
export type LabelOf<Qn> = Qn extends Question<infer L> ? L : string;
/** Answers typed per question: each `value` is that question's label union. */
export type AnswersOf<Q extends Questions> = { readonly [K in keyof Q]: Answer<LabelOf<Q[K]>> };
export type CutsOf<Th extends Thresholds> = { readonly [K in keyof Th]: Cut };

export type Definition<I = unknown, Q extends Questions = Questions, Th extends Thresholds = Thresholds, T = unknown> = {
  readonly contract: string;
  readonly tiers: readonly Tier[];
  readonly input: SchemaAdapter<I>;
  readonly questions: Q;
  /** The formula behind `confidence`, per question type (hashed). Yes/no: Urim derives TypeSafe's normalized
   *  (p_max − 1/n)/(1 − 1/n), n = 2, i.e. |2p − 1|. Choice/score: the vendor's number, formula not specified to Urim. */
  readonly confidence: ConfidenceRule;
  readonly failover: { readonly on: readonly ErrorType[] };
  readonly thresholds: Th;
  /** C (user): input -> input, before encode. Must be pure (D2). */
  prepare?(input: I): I;
  /** C (user): answers + resolved cuts -> value. Must be pure (D2). Throws are rethrown as-is (D11). */
  interpret?(args: { readonly answers: AnswersOf<Q>; readonly cut: CutsOf<Th> }): T;
};

export type PriceTable = {
  readonly id: string; readonly asOf: string; readonly url: string;
  /** perCall: flat estimate (pre-call budget planning). perMInputTokens/perMOutputTokens: price per 1M tokens,
   *  used before the call (estimateInputTokens) and after it (reported usage). null = vendor publishes no price (never invented). */
  readonly entries: Readonly<Record<string, {
    readonly perCall?: number; readonly perMInputTokens?: number | null; readonly perMOutputTokens?: number | null;
    readonly currency: string; readonly source?: string | null;
  }>>;
};
export type Budget = { readonly maxCost: number; readonly currency: string };

/** per_call: flat price-table row. estimated_pre_call: estimateInputTokens(request) x dated token price. null: unknown. */
export type CostSource = "per_call" | "estimated_pre_call";
type StepCost = { readonly costSource: CostSource | null; readonly estimatedInputTokens?: number };
export type PlanStep =
  | ({ readonly tier: Tier; readonly action: "call"; readonly estimatedCost: number | null } & StepCost)
  | ({ readonly tier: Tier; readonly action: "skip"; readonly reason: "budget"; readonly estimatedCost: number } & StepCost);
/** deadlineMs: the effective total deadline (explain only); absent when there is none. */
export type Plan = { readonly contract: string; readonly steps: readonly PlanStep[]; readonly deadlineMs?: number };

export type WireRequest = {
  readonly tierId: string; readonly camp: Camp; readonly path: string; readonly body: unknown;
  /** Descriptor URL template (placeholders like {endpoint} are filled by the adapter); "" when no descriptor. */
  readonly url: string;
};
export type WireReply = {
  readonly status: number; readonly headers: Readonly<Record<string, string>>; readonly body: unknown; readonly latencyMs: number;
};

export type ConfidenceSource = "native" | "urim_derived";
/** typesafe_normalized: |2p − 1| from a yes/no probability (https://docs.typesafe.ai/confidence.md).
 *  vendor_unspecified: the vendor's own number; Urim does not know or assert its formula. */
export type ConfidenceFormula = "typesafe_normalized" | "vendor_unspecified";
export type ConfidenceRule = { readonly noul: "typesafe_normalized"; readonly choice: "vendor_unspecified"; readonly score: "vendor_unspecified" };
export const CONFIDENCE_RULE: ConfidenceRule = Object.freeze({ noul: "typesafe_normalized", choice: "vendor_unspecified", score: "vendor_unspecified" });
export type Answer<L extends string = string> = {
  readonly value: L;
  readonly confidence: number | null;
  /** urim/1 minor addition (slice 4b). native: the vendor returned this confidence. urim_derived: Urim computed it
   *  from vendor probabilities (binary |2p − 1|). null when confidence is null. Absent in older urim/1 envelopes. */
  readonly confidenceSource?: ConfidenceSource | null;
  /** urim/1 minor addition (0.0.1): which formula produced `confidence`; null when confidence is null. Absent in older envelopes. */
  readonly confidenceFormula?: ConfidenceFormula | null;
  readonly native: { readonly name: string; readonly value: unknown; readonly confidence: unknown };
};
export type Answers = Readonly<Record<string, Answer>>;

export type Cut = {
  readonly value: number | null; readonly source: "lock" | "default" | "none";
  readonly passes: boolean; readonly confidence: number | null;
};

/** Eval provenance written by `urim fit` (design §6). */
export type EvalProvenance = {
  readonly setHash: string; readonly n: number; readonly repeat: number; readonly at: string; readonly objectivesMet: boolean;
};
/** Slimmed lock (design §6). `tiers` and `eval` are written by `urim fit`; hand-written locks may omit them. */
export type Lock = {
  readonly lock: 1;
  readonly contract: { readonly id: string; readonly hash: string };
  readonly tiers?: readonly { readonly id: string; readonly descriptorHash: string | null }[];
  readonly cuts: Readonly<Record<string, Readonly<Record<string, number>>>>;
  readonly eval?: EvalProvenance;
};

export type Attempt = { readonly tier: string; readonly outcome: "ok" | "skipped_budget" | ErrorType; readonly latencyMs: number };
export type Fallback = { readonly from: string; readonly reason: ErrorType | "budget"; readonly attempts: number };

export type Usage = {
  readonly inputTokens: number | null; readonly outputTokens: number | null;
  readonly cost: null | {
    readonly amount: number; readonly currency: string; readonly source: "provider" | "estimated";
    readonly priceTable?: { readonly id: string; readonly asOf: string; readonly url: string };
  };
};

export type Envelope = {
  readonly envelope: "urim/1";
  readonly contract: { readonly id: string; readonly hash: string };
  readonly tier: Tier & { readonly role: "primary" | "fallback" };
  readonly answers: Answers;
  readonly thresholds: Readonly<Record<string, Cut>>;
  readonly fallback: Fallback | null;
  readonly attempts: readonly Attempt[];
  readonly usage: Usage;
  readonly requestIds: Readonly<Record<string, string>>;
  readonly at: string;
  readonly raw?: unknown;
  readonly interpretFailed?: true;
};

export type Success<T, C = Readonly<Record<string, Cut>>> = {
  readonly ok: true; readonly value: T; readonly envelope: Envelope;
  readonly fallback: Fallback | null; readonly thresholds: C;
};
export type Failure = { readonly ok: false; readonly error: import("./errors.ts").UrimError; readonly attempts: readonly Attempt[] };
export type Result<T, C = Readonly<Record<string, Cut>>> = Success<T, C> | Failure;

/**
 * D3: the one record onSettled receives for EVERY settled decide call (success, interpret defect, abstain).
 * Uniform key set across outcomes; deep-frozen. `envelope` is null when no tier answered.
 */
export type Settled = {
  readonly settled: "urim/1";
  readonly outcome: "ok" | "interpret_failed" | "abstain";
  readonly contract: { readonly id: string; readonly hash: string | null };
  readonly envelope: Envelope | null;
  readonly error: { readonly type: ErrorType; readonly message: string; readonly tier: string | null } | null;
  readonly attempts: readonly Attempt[];
  readonly at: string;
};
