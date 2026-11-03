// Fit fixture: one noul question, one threshold, two tiers. Confidences in fake.fit.json are hand-picked so the
// fitted cutoffs are hand-checkable (see fit.test.ts). PLACEHOLDER data.
import { defineDecision, noul, threshold } from "../../src/index.ts";
import { JEV, CLEF, inputSchema } from "../fixtures.ts";

export const gate = defineDecision({
  contract: "fit-gate@1.0.0",
  tiers: [JEV, CLEF],
  input: inputSchema,
  questions: { page: noul("Page?", { yes: "y", no: "n" }) },
 
  failover: { on: [] },
  thresholds: { gate: threshold({ on: "page", objective: { minPrecision: 0.75 } }) },
});
export const notADecision = { hello: "world" };
