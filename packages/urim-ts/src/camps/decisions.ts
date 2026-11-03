// C: the OpenAI decisions body (also AI Gateway /v1/decisions and LiteLLM's decisions route).
// Sources: https://developers.openai.com/api/reference/typescript/resources/decisions/methods/create/index.md (request),
// https://cdn.jsdelivr.net/npm/openai@7.35.0/resources/decisions.d.mts (response). Checked 2026-10-28 EDT.
// TODO(vendor-fact): OpenAI's confidence formula is undocumented; native choice/score confidence passes through as-is.
import { UrimError } from "../errors.ts";
import type { Definition, Question, QuestionType, Tier } from "../types.ts";
import { argmax, binaryConfidence, binaryLabel, isRecord, nonconformant, num, toAnswers,
  type Decoded, type DecodeOptions, type RawAnswer, vendorConfidence } from "./shared.ts";

export const PATH = "/v1/decisions";

const NATIVE_TYPE: Readonly<Record<QuestionType, string>> = { noul: "predicate", choice: "choice", score: "score" };

const encodeQuestion = (name: string, q: Question): Record<string, unknown> => {
  const entries = Object.entries(q.options);
  const base = { type: NATIVE_TYPE[q.type], name, instructions: q.prompt };
  switch (q.type) {
    case "choice": return { ...base, choices: entries.map(([value, description]) => ({ value, description })) };
    case "score": return { ...base, levels: entries.map(([label, description]) => ({ label, description })) };
    case "noul": return base; // predicates carry no yes/no descriptions (O2): those texts are not sent
  }
};

export const encode = (def: Definition, wireModel: string, input: unknown): unknown => ({
  model: wireModel,
  // TODO(vendor-fact): exact message item wrapper (whether `type: "message"` is required) is medium confidence.
  input: [{ role: "user", content: [{ type: "input_json", data: input }] }],
  questions: Object.entries(def.questions).map(([name, q]) => encodeQuestion(name, q)),
});

const decodeOne = (name: string, a: Record<string, unknown>, sentinel: boolean): RawAnswer | undefined => {
  switch (a["type"]) {
    case "predicate": {
      const p = num(a["probability"]);
      if (p === null) return undefined;
      // Confidence: TypeSafe's binary formula applied client-side (OpenAI returns none for predicates).
      return { name, label: binaryLabel(p), confidence: binaryConfidence(p), nativeValue: p, nativeConfidence: null, confidenceSource: "urim_derived" };
    }
    case "choice": // a boolean choice never equals a string label, so it falls out as nonconformant
      return { name, label: a["choice"], confidence: vendorConfidence(a, sentinel), nativeValue: a["choice"], nativeConfidence: a["confidence"], confidenceSource: "native" };
    case "score": {
      const probs = Array.isArray(a["probabilities"]) ? a["probabilities"].filter(isRecord) : [];
      const top = probs[argmax(probs.map((p) => num(p["probability"]) ?? -1))];
      return { name, label: top?.["label"], confidence: vendorConfidence(a, sentinel), nativeValue: a["score"], nativeConfidence: a["confidence"], confidenceSource: "native" };
    }
    default: return undefined;
  }
};

export const decode = (def: Definition, tier: Tier, body: unknown, opts: DecodeOptions = {}): Decoded => {
  if (!isRecord(body) || !Array.isArray(body["answers"])) return nonconformant(tier, "response has no answers array");
  const list = body["answers"];
  const names = Object.keys(def.questions);
  const raws = new Map<string, RawAnswer>();
  for (const [i, a] of list.entries()) {
    if (!isRecord(a)) continue;
    const name = typeof a["name"] === "string" ? a["name"] : names[i]; // null name: answers come in question order
    if (name === undefined || !(name in def.questions)) continue;
    if (a["type"] === "refusal") {
      return { ok: false, error: new UrimError("refused", `${tier.id} refused question "${name}"`, { tier: tier.id }) };
    }
    const raw = decodeOne(name, a, opts.unavailableSentinel === true);
    if (raw !== undefined) raws.set(name, raw);
  }
  return toAnswers(def, tier, raws, body);
};
