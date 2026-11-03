// Wire fixtures shaped from the vendor references checked 2026-10-28 EDT.
// The research file records field shapes, not verbatim example payloads, so these bodies are
// RECONSTRUCTED from the documented field lists (values are ours). Each cites its source URL.

/** systemone noul answer: P(yes) only, no confidence. */
export const s1Noul = (p: number) => ({ type: "noul", noul: p });
/** systemone choice answer. */
export const s1Choice = (choice: string, confidence: number, probabilities: Record<string, number>) =>
  ({ type: "choice", choice, confidence, probabilities });
/** systemone score answer: expected index + legend + probabilities keyed "0".."n-1". */
export const s1Score = (score: number, confidence: number, probabilities: Record<string, number>, legend: Record<string, string>) =>
  ({ type: "score", score, confidence, legend, probabilities });
/** systemone response. */
export const s1Body = (answers: Record<string, unknown>, model?: string) =>
  ({ ...(model === undefined ? {} : { model }), answers, usage: { input_tokens: 1200, output_tokens: 3 } });

/** Triage answer set used across client tests: page yes (p=0.95 -> conf 0.9), team data. */
export const triageOk = (teamConf = 0.9, team = "data", model?: string) => s1Body({
  page: s1Noul(0.95),
  team: s1Choice(team, teamConf, { billing: 0.02, platform: 0.03, identity: 0.02, [team]: 0.93 }),
}, model);

/** decisions answers. https://cdn.jsdelivr.net/npm/openai@7.35.0/resources/decisions.d.mts */
export const dPredicate = (name: string | null, probability: number) => ({ type: "predicate", name, probability });
export const dChoice = (name: string | null, choice: string | boolean, confidence: number, probabilities: Array<{ value: string | boolean; probability: number }>) =>
  ({ type: "choice", name, choice, confidence, probabilities });
export const dScore = (name: string | null, score: number, confidence: number, probabilities: Array<{ value: number; label: string; probability: number }>) =>
  ({ type: "score", name, score, confidence, probabilities });
export const dRefusal = (name: string | null) => ({ type: "refusal", name });
/** decisions response. https://developers.openai.com/api/reference/typescript/resources/decisions/methods/create/index.md */
export const dBody = (answers: unknown[]) =>
  ({ model: "gpt-6-luna", answers, usage: { input_tokens: 800, output_tokens: 0, total_tokens: 800 } });
