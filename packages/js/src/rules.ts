// Cross-field rules, run after the closed schema has passed (CONTRACT.md C-097, C-099).
// Same order as rules.rs/rules.py. The schema has already fixed every shape, so the accessors
// below only distinguish "present" from "absent" (an absent optional key reads as null).
// Implements: C-097, C-099
import { sanitize } from "./display.js";
import { Failure, Problem } from "./problem.js";
import type { Value, YamlMap } from "./profile.js";
import { isYamlMap } from "./profile.js";
import { EMULATIONS, EXPERIMENTAL_QUESTION_TYPES } from "./schema.gen.js";
import type { Path } from "./schema.js";
import { pathText } from "./schema.js";

/** `v[key]` of a mapping or a list; null when absent. */
function get(v: Value, key: Value): Value {
  if (isYamlMap(v)) return v.strings.get(String(key)) ?? null;
  if (Array.isArray(v)) return v[Number(key)] ?? null;
  return null;
}

/** The entries of a mapping (by key) or a list (by index); none when absent. */
function entries(v: Value): (readonly [string | number, Value])[] {
  if (isYamlMap(v)) return [...v.strings];
  if (Array.isArray(v)) return v.map((item: Value, i: number) => [i, item] as const);
  return [];
}

const fail = (message: string): never => {
  throw new Failure(message);
};

const CANONICAL_INDEX = /^(?:0|[1-9][0-9]*)$/;

/** Whether `answer` is an answer of `question` (SPEC §5.4): an option key, yes/no, or a level index. */
function isAnswer(question: Value, answer: string): boolean {
  switch (get(question, "type")) {
    case "choice":
      return get(get(question, "options"), answer) !== null;
    case "yesno":
      return answer === "yes" || answer === "no";
    case "score":
      return CANONICAL_INDEX.test(answer) && get(get(question, "levels"), answer) !== null;
    default:
      return false;
  }
}

/** An extension's `fallback: {emulate: name}`: no emulation is registered for extensions in 0.2. */
function extensionFallback(path: Path, ext: Value): void {
  const name = get(get(ext, "fallback"), "emulate");
  if (typeof name === "string")
    fail(Problem.noEmulation(pathText([...path, "fallback", "emulate"]), sanitize(name)));
}

/** The contract rules, in this order: question types, policy, eval, requires/prefers, emulations. */
export function contractRules(root: YamlMap): void {
  const requires = get(root, "requires");
  const prefers = get(root, "prefers");
  const questions = get(root, "questions");
  for (const [name, question] of entries(questions)) {
    const experimental = EXPERIMENTAL_QUESTION_TYPES.find((t) => t === get(question, "type"));
    const declaration = `question_types.${experimental}`;
    if (
      experimental !== undefined &&
      get(requires, declaration) === null &&
      get(prefers, declaration) === null
    ) {
      fail(Problem.undeclaredExperimental(pathText(["questions", name, "type"]), experimental));
    }
  }
  for (const [id, rule] of entries(get(root, "policy"))) {
    const name = get(rule, "question");
    const question = get(questions, name);
    if (question === null)
      fail(Problem.unknownQuestion(pathText(["policy", id, "question"]), sanitize(String(name))));
    const answer = get(get(rule, "when"), "answer");
    if (typeof answer === "string" && !isAnswer(question, answer)) {
      fail(Problem.notAnAnswer(pathText(["policy", id, "when", "answer"]), sanitize(String(name))));
    }
  }
  for (const [name] of entries(get(get(root, "eval"), "paraphrases"))) {
    if (get(questions, name) === null) {
      fail(Problem.unknownQuestion(pathText(["eval", "paraphrases", name]), sanitize(String(name))));
    }
  }
  for (const [cap] of entries(requires)) {
    if (get(prefers, cap) !== null) fail(Problem.alsoPreferred(pathText(["requires", cap])));
  }
  for (const [cap, preference] of entries(prefers)) {
    const name = get(get(preference, "fallback"), "emulate");
    if (typeof name === "string" && !(EMULATIONS.get(String(cap)) ?? []).includes(name)) {
      fail(Problem.noEmulation(pathText(["prefers", cap, "fallback", "emulate"]), sanitize(name)));
    }
  }
  for (const [key, ext] of entries(root)) if (String(key).startsWith("x-")) extensionFallback([key], ext);
  for (const [name, question] of entries(questions)) {
    for (const [key, ext] of entries(question)) {
      if (String(key).startsWith("x-")) extensionFallback(["questions", name, key], ext);
    }
  }
}

/** The lockfile rules: every `active` and `standby` target is a key of that contract's `targets`. */
export function lockfileRules(root: YamlMap): void {
  for (const [id, entry] of entries(get(root, "contracts"))) {
    const targets = get(entry, "targets");
    const where = pathText(["contracts", id, "targets"]);
    const active = get(entry, "active");
    if (get(targets, active) === null) {
      fail(Problem.notATarget(pathText(["contracts", id, "active"]), sanitize(String(active)), where));
    }
    for (const [i, target] of entries(get(entry, "standby"))) {
      if (get(targets, target) === null) {
        fail(Problem.notATarget(pathText(["contracts", id, "standby", i]), sanitize(String(target)), where));
      }
    }
  }
}
