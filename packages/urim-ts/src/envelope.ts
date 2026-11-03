// C: assemble the portable envelope. Provider values pass through untouched; fallback is never silent (C32).
import { deepFreeze } from "./freeze.ts";
import type { Answers, Attempt, Cut, Definition, Envelope, Fallback, PriceTable, Tier, Usage } from "./types.ts";

export type EnvelopeParts = {
  readonly def: Definition; readonly contractHash: string; readonly tier: Tier; readonly answers: Answers;
  readonly cuts: Readonly<Record<string, Cut>>; readonly attempts: readonly Attempt[];
  readonly requestIds: Readonly<Record<string, string>>; readonly at: string;
  readonly prices?: PriceTable; readonly providerUsage?: Usage; readonly raw?: unknown; readonly interpretFailed?: boolean;
};

const fallbackFor = (def: Definition, tier: Tier, attempts: readonly Attempt[]): Fallback | null => {
  const primary = def.tiers[0];
  if (primary === undefined || primary.id === tier.id) return null;
  const failed = attempts.filter((a) => a.tier !== tier.id);
  const first = failed.find((a) => a.tier === primary.id) ?? failed[0];
  const reason = first === undefined || first.outcome === "ok" ? "provider_unavailable"
    : first.outcome === "skipped_budget" ? "budget" : first.outcome;
  return { from: primary.id, reason, attempts: failed.length };
};

type PriceEntry = PriceTable["entries"][string];
/** Token price wins over flat per-call; output tokens priced only when the table says so (all vendors: free). */
const estimate = (e: PriceEntry, reported: Usage | undefined): number | null => {
  if (e.perMInputTokens !== undefined) {
    const inTok = reported?.inputTokens;
    if (e.perMInputTokens === null || inTok == null) return null;
    return (inTok * e.perMInputTokens + (reported?.outputTokens ?? 0) * (e.perMOutputTokens ?? 0)) / 1_000_000;
  }
  return e.perCall ?? null;
};

/** Provider-reported cost wins; else estimate from a dated price table; else null. Never invented. */
const usageFor = (tier: Tier, prices: PriceTable | undefined, reported: Usage | undefined): Usage => {
  if (reported?.cost != null) return reported;
  const entry = prices?.entries[tier.id];
  const amount = entry === undefined ? null : estimate(entry, reported);
  const cost = entry === undefined || prices === undefined || amount === null ? null : {
    amount, currency: entry.currency, source: "estimated" as const,
    priceTable: { id: prices.id, asOf: prices.asOf, url: prices.url },
  };
  return { inputTokens: reported?.inputTokens ?? null, outputTokens: reported?.outputTokens ?? null, cost };
};

export const buildEnvelope = (p: EnvelopeParts): Envelope => {
  const fallback = fallbackFor(p.def, p.tier, p.attempts);
  return deepFreeze({
    envelope: "urim/1" as const,
    contract: { id: p.def.contract, hash: p.contractHash },
    tier: { ...p.tier, role: fallback === null ? "primary" as const : "fallback" as const },
    answers: p.answers, thresholds: p.cuts, fallback, attempts: [...p.attempts],
    usage: usageFor(p.tier, p.prices, p.providerUsage),
    requestIds: { ...p.requestIds }, at: p.at,
    ...(p.raw === undefined ? {} : { raw: structuredClone(p.raw) }),
    ...(p.interpretFailed === true ? { interpretFailed: true as const } : {}),
  });
};
