// C: resolve each named threshold for the tier that answered (D4). interpret receives the result as data.
import { UrimError } from "./errors.ts";
import type { Answers, Cut, Definition, Lock, Threshold, Tier } from "./types.ts";

export type CutContext = { readonly mode: "dev" | "prod"; readonly lock?: Lock };

const cutValue = (name: string, t: Threshold, tier: Tier, ctx: CutContext): Pick<Cut, "value" | "source"> => {
  const locked = ctx.lock?.cuts[name]?.[tier.id];
  if (locked !== undefined) return { value: locked, source: "lock" };
  if (t.default !== null) return { value: t.default, source: "default" };
  if (ctx.mode === "prod") throw new UrimError("lock_violation", `threshold "${name}" has no cutoff for ${tier.id}`, { tier: tier.id });
  return { value: null, source: "none" };
};

/** Missing confidence against a real cutoff escalates (passes:false); no cutoff passes through. */
const passes = (value: number | null, confidence: number | null): boolean => {
  if (value === null) return true;
  if (confidence === null) return false;
  return confidence >= value;
};

export const resolveCuts = (def: Definition, tier: Tier, answers: Answers, ctx: CutContext): Record<string, Cut> =>
  Object.fromEntries(Object.entries(def.thresholds).map(([name, t]) => {
    const { value, source } = cutValue(name, t, tier, ctx);
    const confidence = answers[t.on]?.confidence ?? null;
    return [name, { value, source, passes: passes(value, confidence), confidence }];
  }));
