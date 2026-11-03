// C: the systemone body (TypeSafe reference; also Microsoft, Cloudflare, Liquid, Perplexity, Fastino, Inception).
// Source: https://docs.typesafe.ai/api/system-one (checked 2026-10-28 EDT).
import type { Definition, Question, Tier } from "../types.ts";
import { argmax, binaryConfidence, binaryLabel, isRecord, nonconformant, num, scoreLabels, toAnswers,
  type Decoded, type DecodeOptions, type RawAnswer, vendorConfidence } from "./shared.ts";

export const PATH = "/v1/systemone";

const criteria = (q: Question): unknown => {
  switch (q.type) {
    case "choice": return { ...q.options };
    case "score": return Object.values(q.options); // ordered; index = level from 0
    case "noul": return { true: (q.options as Record<string, string>)["yes"], false: (q.options as Record<string, string>)["no"] };
  }
};

export const encode = (def: Definition, wireModel: string, state: unknown): unknown => ({
  model: wireModel,
  state,
  questions: Object.fromEntries(Object.entries(def.questions)
    .map(([name, q]) => [name, { type: q.type, instructions: q.prompt, criteria: criteria(q) }])),
});

const decodeOne = (name: string, q: Question, a: unknown, sentinel: boolean): RawAnswer | undefined => {
  if (!isRecord(a)) return undefined;
  switch (q.type) {
    case "noul": {
      const p = num(a["noul"]);
      if (p === null) return undefined;
      return { name, label: binaryLabel(p), confidence: binaryConfidence(p), nativeValue: p, nativeConfidence: null, confidenceSource: "urim_derived" };
    }
    case "choice":
      return { name, label: a["choice"], confidence: vendorConfidence(a, sentinel), nativeValue: a["choice"], nativeConfidence: a["confidence"], confidenceSource: "native" };
    case "score": {
      const labels = scoreLabels(q);
      const probs = isRecord(a["probabilities"]) ? a["probabilities"] : {};
      const ps = labels.map((_, i) => num(probs[String(i)]) ?? -1);
      const label = ps.every((p) => p < 0) ? undefined : labels[argmax(ps)];
      return { name, label, confidence: vendorConfidence(a, sentinel), nativeValue: a["score"], nativeConfidence: a["confidence"], confidenceSource: "native" };
    }
  }
};

export const decode = (def: Definition, tier: Tier, body: unknown, opts: DecodeOptions = {}): Decoded => {
  if (!isRecord(body) || !isRecord(body["answers"])) return nonconformant(tier, "response has no answers map");
  const answers = body["answers"];
  const raws = new Map<string, RawAnswer>();
  for (const [name, q] of Object.entries(def.questions)) {
    const raw = decodeOne(name, q, answers[name], opts.unavailableSentinel === true);
    if (raw !== undefined) raws.set(name, raw);
  }
  return toAnswers(def, tier, raws, body);
};
