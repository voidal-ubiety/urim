// C: helpers shared by the camp codecs: label-space checks, the binary confidence rule, usage.
import { UrimError } from "../errors.ts";
import type { Answer, Answers, ConfidenceSource, Definition, Question, Tier } from "../types.ts";

/** Per-descriptor decode options. unavailableSentinel: the provider sends confidence 0 + empty probabilities for "unavailable". */
export type DecodeOptions = { readonly unavailableSentinel?: boolean };

/** A decoded native answer, already reduced to a candidate label. */
export type RawAnswer = {
  readonly name: string; readonly label: unknown; readonly confidence: number | null;
  readonly nativeValue: unknown; readonly nativeConfidence: unknown;
  /** Who computed `confidence`: the vendor ("native") or Urim from vendor probabilities ("urim_derived"). */
  readonly confidenceSource: ConfidenceSource;
};
export type TokenUsage = { readonly inputTokens: number | null; readonly outputTokens: number | null };
export type Decoded =
  | { ok: true; answers: Answers; usage: TokenUsage | null; model: string | null }
  | { ok: false; error: UrimError };

export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
/** A vendor confidence; with the sentinel flag, 0 plus present-but-empty probabilities ({} or []) means "unavailable" -> null. */
export const vendorConfidence = (a: Record<string, unknown>, unavailableSentinel: boolean): number | null => {
  const c = num(a["confidence"]);
  if (!unavailableSentinel || c !== 0) return c;
  const p = a["probabilities"];
  const empty = Array.isArray(p) ? p.length === 0 : isRecord(p) && Object.keys(p).length === 0;
  return empty ? null : c;
};
const unit = (v: unknown): number | null => { const n = num(v); return n !== null && n >= 0 && n <= 1 ? n : null; };

export const nonconformant = (tier: Tier, message: string): { ok: false; error: UrimError } =>
  ({ ok: false, error: new UrimError("nonconformant_response", message, { tier: tier.id }) });

/** P(yes) -> label. A tie (0.5) reads "yes"; its confidence is 0, so no threshold can pass on it. */
export const binaryLabel = (p: number): "yes" | "no" => (p >= 0.5 ? "yes" : "no");

/** TypeSafe's documented confidence (p_max − 1/n)/(1 − 1/n) with n = 2, i.e. |2p − 1|.
 *  https://docs.typesafe.ai/confidence.md — computed client-side; the vendor does not return it. */
export const binaryConfidence = (p: number): number =>
  Math.round(((Math.max(p, 1 - p) - 0.5) / 0.5) * 1e12) / 1e12; // 12-dp rounding removes float noise (0.95 -> 0.9, not 0.8999...)

/** Index of the largest probability; first wins on a tie. */
export const argmax = (ps: readonly number[]): number =>
  ps.reduce((best, p, i) => (p > (ps[best] ?? -Infinity) ? i : best), 0);

export const usageOf = (body: Record<string, unknown>): TokenUsage | null => {
  const u = body["usage"];
  return isRecord(u) ? { inputTokens: num(u["input_tokens"]), outputTokens: num(u["output_tokens"]) } : null;
};

export const scoreLabels = (q: Question): readonly string[] => Object.keys(q.options);

/** Checks every question is answered inside its label space; never alters native values. */
export const toAnswers = (def: Definition, tier: Tier, raws: ReadonlyMap<string, RawAnswer>,
  body: Record<string, unknown>): Decoded => {
  const answers: Record<string, Answer> = {};
  for (const [name, q] of Object.entries(def.questions)) {
    const raw = raws.get(name);
    if (raw === undefined) return nonconformant(tier, `question "${name}" not answered`);
    if (typeof raw.label !== "string" || !(raw.label in q.options)) {
      return nonconformant(tier, `question "${name}" answered outside its labels`);
    }
    const confidence = unit(raw.confidence);
    answers[name] = { value: raw.label, confidence, confidenceSource: confidence === null ? null : raw.confidenceSource,
      confidenceFormula: confidence === null ? null : raw.confidenceSource === "urim_derived" ? "typesafe_normalized" : "vendor_unspecified",
      native: { name: raw.name, value: raw.nativeValue, confidence: raw.nativeConfidence ?? null } };
  }
  const model = typeof body["model"] === "string" ? body["model"] : null;
  return { ok: true, answers, usage: usageOf(body), model };
};
