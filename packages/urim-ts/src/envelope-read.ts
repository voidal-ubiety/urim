// C: consumer-side reader for the urim/1 envelope (design §5.2/§5.5). Checks required members, ignores unknown ones,
// rejects other major versions. This is what downstream services should rely on — not on exact key sets.
import type { Issue } from "./errors.ts";
import type { Envelope } from "./types.ts";

export type EnvelopeRead = { ok: true; envelope: Envelope } | { ok: false; issues: readonly Issue[] };
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

export const readEnvelope = (v: unknown): EnvelopeRead => {
  if (!isObj(v)) return { ok: false, issues: [{ path: "$", message: "envelope must be an object" }] };
  const issues: Issue[] = [];
  const need = (path: string, okay: boolean, message: string) => { if (!okay) issues.push({ path, message }); };
  need("envelope", v["envelope"] === "urim/1", "unsupported envelope version (this reader speaks urim/1)");
  const c = v["contract"]; need("contract", isObj(c) && typeof c["id"] === "string" && typeof c["hash"] === "string", "needs {id, hash}");
  const t = v["tier"]; need("tier", isObj(t) && typeof t["id"] === "string" && (t["role"] === "primary" || t["role"] === "fallback"), "needs {id, role}");
  const a = v["answers"];
  need("answers", isObj(a) && Object.values(a).every((x) => isObj(x) && typeof x["value"] === "string"
    && (x["confidence"] === null || typeof x["confidence"] === "number") && isObj(x["native"])
    && (x["confidenceSource"] === undefined || x["confidenceSource"] === null || x["confidenceSource"] === "native" || x["confidenceSource"] === "urim_derived")
    && (x["confidenceFormula"] === undefined || x["confidenceFormula"] === null || x["confidenceFormula"] === "typesafe_normalized" || x["confidenceFormula"] === "vendor_unspecified")),
    "each answer needs {value, confidence: number|null, native} an optional confidenceSource: native|urim_derived|null and an optional confidenceFormula: typesafe_normalized|vendor_unspecified|null");
  need("thresholds", isObj(v["thresholds"]), "must be an object");
  need("fallback", v["fallback"] === null || isObj(v["fallback"]), "must be null or an object");
  need("attempts", Array.isArray(v["attempts"]), "must be an array");
  need("usage", isObj(v["usage"]), "must be an object");
  need("requestIds", isObj(v["requestIds"]), "must be an object");
  need("at", typeof v["at"] === "string", "must be an ISO string");
  return issues.length > 0 ? { ok: false, issues } : { ok: true, envelope: v as unknown as Envelope };
};
