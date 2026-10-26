// `urim check`: validate a hoshen lockfile or a contract's top-level shape. Same as
// check.rs/check.py. Every string that reaches the output line goes through `sanitize` (C-089).
// Implements: C-003, C-006, C-040..C-046, C-050..C-057, C-060, C-070, C-071, C-088, C-089, C-093, C-094
import { hasInvisible, sanitize } from "./display.js";
import { Failure, Problem, RENAMED_KEY, SUPPORTED_HOSHEN } from "./problem.js";
import type { Value, YamlMap } from "./profile.js";
import { isYamlMap, parseDocument } from "./profile.js";
import { readText } from "./read.js";

export { SUPPORTED_HOSHEN };

const CONTRACT_REQUIRED = ["contract", "version", "state", "questions"] as const;

export interface CheckResult {
  ok: boolean;
  line: string;
  exitCode: 0 | 1;
}

const fail = (file: string, problem: string): CheckResult => ({
  ok: false,
  line: `${sanitize(file)}: error: ${problem}`,
  exitCode: 1,
});
const pass = (file: string, detail: string): CheckResult => ({
  ok: true,
  line: `${sanitize(file)}: ok (${detail})`,
  exitCode: 0,
});

/** The string value of identifier `name`; invisible (C-088), then non-ASCII (C-092), characters are refused. */
function identifier(root: YamlMap, name: string): string {
  const value = root.strings.get(name);
  if (typeof value !== "string") throw new Failure(Problem.notAString(name));
  if (hasInvisible(value)) throw new Failure(Problem.invisibleIn(name));
  // Any UTF-16 code unit above 0x7F means a character above U+007F.
  if (value.split("").some((unit) => unit.charCodeAt(0) > 0x7f)) throw new Failure(Problem.nonAsciiIn(name));
  return value;
}

function lockfile(root: YamlMap, hoshen: Value): string {
  if (typeof hoshen !== "bigint") throw new Failure(Problem.hoshenNotInteger);
  if (hoshen === 1n) throw new Failure(Problem.hoshenNeverReleased);
  if (!SUPPORTED_HOSHEN.includes(hoshen)) throw new Failure(Problem.unsupportedHoshen(hoshen));
  if (!root.strings.has("urim")) throw new Failure(Problem.missingKeys(["urim"]));
  return `lockfile, hoshen ${hoshen}, urim ${sanitize(identifier(root, "urim"))}`;
}

function contract(root: YamlMap): string {
  const specVersion = identifier(root, "urim");
  const missing = CONTRACT_REQUIRED.filter((k) => !root.strings.has(k));
  if (missing.length > 0) throw new Failure(Problem.missingKeys(missing));
  const id = identifier(root, "contract");
  const version = identifier(root, "version");
  if (!isYamlMap(root.strings.get("state"))) throw new Failure(Problem.stateNotMapping);
  const questions = root.strings.get("questions");
  if (!isYamlMap(questions) || questions.size === 0) throw new Failure(Problem.questionsEmpty);
  return `contract ${sanitize(id)}@${sanitize(version)}, urim ${sanitize(specVersion)}`;
}

function detail(text: string): string {
  const root = parseDocument(text);
  if (!isYamlMap(root)) throw new Failure(Problem.rootNotMapping);
  if (root.strings.has(RENAMED_KEY)) throw new Failure(Problem.renamedKey);
  if (root.strings.has("hoshen")) return lockfile(root, root.strings.get("hoshen") as Value);
  if (root.strings.has("urim")) return contract(root);
  throw new Failure(Problem.notUrim);
}

/** Run `fn`, turning a `Failure` into a failed result; anything else is a bug and propagates. */
function run(file: string, fn: () => string): CheckResult {
  try {
    return pass(file, fn());
  } catch (e) {
    if (e instanceof Failure) return fail(file, e.message);
    throw e;
  }
}

/** Check YAML `text`. `file` is used only in the message (C-070). */
export function checkText(file: string, text: string): CheckResult {
  return run(file, () => detail(text));
}

/** Read the file at `path` (strict UTF-8, regular file, at most MAX_BYTES) and check it. */
export function checkFile(path: string): CheckResult {
  return run(path, () => detail(readText(path)));
}
