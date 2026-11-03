// C: definition helpers. Each returns frozen data; invalid shapes throw invalid_definition at module load.
import { DESCRIPTORS } from "./descriptors.ts";
import { FAILOVER_TYPES, invalidDefinition, type Issue } from "./errors.ts";
import { deepFreeze } from "./freeze.ts";
import type { AnswersOf, Camp, Definition, Objective, Question, QuestionType, Questions, Threshold, Thresholds, Tier } from "./types.ts";
import { CONFIDENCE_RULE, type ConfidenceRule } from "./types.ts";

const EXACT_VERSION = /^[0-9A-Za-z][0-9A-Za-z.\-_]*$/;

export const tier = (spec: Omit<Tier, "id"> & { camp: Camp }): Tier => {
  if (!EXACT_VERSION.test(spec.version)) {
    throw invalidDefinition([{ path: "version", message: `exact version required, got "${spec.version}"` }]);
  }
  return deepFreeze({ id: `${spec.provider}/${spec.model}@${spec.version}`, ...spec, questionTypes: [...spec.questionTypes] });
};

const question = <L extends string>(type: QuestionType, prompt: string, options: Record<L, string>): Question<L> => {
  if (Object.keys(options).length < 2) throw invalidDefinition([{ path: prompt, message: `${type} needs at least two options` }]);
  return deepFreeze({ type, prompt, options: { ...options } });
};

export const noul = (prompt: string, labels: { yes: string; no: string }): Question<"yes" | "no"> =>
  question("noul", prompt, { yes: labels.yes, no: labels.no });
export const choice = <L extends string>(prompt: string, options: Record<L, string>): Question<L> =>
  question("choice", prompt, options);
/** Levels in ascending order; key order is the order. */
export const score = <L extends string>(prompt: string, levels: Record<L, string>): Question<L> =>
  question("score", prompt, levels);

export const threshold = (spec: { on: string; default?: number; objective?: Objective }): Threshold => {
  const value = spec.default ?? null;
  if (value !== null && !(value >= 0 && value <= 1)) {
    throw invalidDefinition([{ path: spec.on, message: `default must be within 0..1, got ${value}` }]);
  }
  return deepFreeze({ on: spec.on, default: value, objective: { ...spec.objective } });
};

const tierIssues = (def: Definition): Issue[] => {
  if (def.tiers.length === 0) return [{ path: "tiers", message: "at least one tier required" }];
  const ids = def.tiers.map((t) => t.id);
  const duplicates = ids.filter((id, i) => ids.indexOf(id) !== i).map((id) => ({ path: "tiers", message: `duplicate tier ${id}` }));
  const unsupported = def.tiers.flatMap((t) => Object.entries(def.questions)
    .filter(([, q]) => !t.questionTypes.includes(q.type))
    .map(([name, q]) => ({ path: `questions.${name}`, message: `${t.id} cannot answer ${q.type}` })));
  const wrongCamp = def.tiers.filter((t) => DESCRIPTORS[t.provider] !== undefined && DESCRIPTORS[t.provider]?.camp !== t.camp)
    .map((t) => ({ path: "tiers", message: `${t.id}: ${t.provider} speaks the ${DESCRIPTORS[t.provider]?.camp} body, not ${t.camp}` }));
  return [...duplicates, ...unsupported, ...wrongCamp];
};

const thresholdIssues = (def: Definition): Issue[] =>
  Object.entries(def.thresholds)
    .filter(([, t]) => !(t.on in def.questions))
    .map(([name, t]) => ({ path: `thresholds.${name}`, message: `unknown question "${t.on}"` }));

const failoverIssues = (def: Definition): Issue[] =>
  def.failover.on.filter((t) => !FAILOVER_TYPES.has(t))
    .map((t) => ({ path: "failover.on", message: `"${t}" can never fail over` }));

export const defineDecision = <I, Q extends Questions, Th extends Thresholds, T = AnswersOf<Q>>(
  spec: Omit<Definition<I, Q, Th, T>, "confidence"> & { readonly confidence?: ConfidenceRule }): Definition<I, Q, Th, T> => {
  // `confidence` is fixed by Urim (it names what the codecs compute); a caller value is ignored.
  const def: Definition<I, Q, Th, T> = { ...spec, confidence: CONFIDENCE_RULE };
  const issues = [...tierIssues(def), ...thresholdIssues(def), ...failoverIssues(def)];
  if (issues.length > 0) throw invalidDefinition(issues);
  return deepFreeze({ ...def, failover: { on: [...def.failover.on] } });
};
