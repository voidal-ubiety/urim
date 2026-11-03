// C: `urim emit` as a pure function. Definition -> canonical contract JSON + hash. No network, no files.
import { canonicalize, sha256 } from "./canonical.ts";
import type { Definition } from "./types.ts";

export type Emitted = { readonly document: unknown; readonly json: string; readonly hash: string };

/** Options are an ordered list so score level order is part of the contract; hooks count by presence only. */
const contractDocument = (def: Definition): unknown => ({
  urimContract: 1,
  contract: def.contract,
  tiers: def.tiers.map((t) => ({ id: t.id, provider: t.provider, model: t.model, version: t.version, camp: t.camp })),
  input: def.input.toJSONSchema(),
  questions: Object.fromEntries(Object.entries(def.questions).map(([name, q]) => [name, {
    type: q.type, prompt: q.prompt,
    options: Object.entries(q.options).map(([label, description]) => ({ label, description })),
  }])),
  confidence: def.confidence,
  failover: { on: [...def.failover.on].sort() },
  thresholds: def.thresholds,
  hooks: { prepare: def.prepare !== undefined, interpret: def.interpret !== undefined },
});

export const emit = (def: Definition): Emitted => {
  const document = contractDocument(def);
  const json = canonicalize(document);
  return Object.freeze({ document, json, hash: sha256(json) });
};
