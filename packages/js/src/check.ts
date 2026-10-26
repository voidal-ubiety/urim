// `urim check`: validate a hoshen 2 lockfile or a urim 0.2 contract against the closed schema. Same as
// check.rs/check.py. Every string that reaches the output line goes through `sanitize` (C-089).
// Implements: C-003, C-006, C-040, C-041, C-042, C-060, C-070, C-071, C-088, C-089, C-093..C-099
import { sanitize } from "./display.js";
import { integrityOf } from "./jcs.js";
import { Failure, Problem, RENAMED_KEY, SUPPORTED_HOSHEN } from "./problem.js";
import type { Value, YamlMap } from "./profile.js";
import { isYamlMap, parseDocument } from "./profile.js";
import { readText } from "./read.js";
import { contractRules, lockfileRules } from "./rules.js";
import { CONTRACT, FORMATS, LOCKFILE, PROTOCOL } from "./schema.gen.js";
import { checkString, validate } from "./schema.js";

export { SUPPORTED_HOSHEN };

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

/** The `urim` gate (SPEC §5.1.1): a protocol version, then exactly the one this checker supports. */
function urimGate(root: YamlMap): void {
  const value = checkString(
    ["urim"],
    root.strings.get("urim") ?? null,
    "protocol_version",
    FORMATS.protocol_version,
  );
  if (value !== PROTOCOL) throw new Failure(Problem.unsupportedUrim(value));
}

function lockfile(root: YamlMap, hoshen: Value): string {
  if (typeof hoshen !== "bigint") throw new Failure(Problem.hoshenNotInteger);
  if (hoshen === 1n) throw new Failure(Problem.hoshenNeverReleased);
  if (!SUPPORTED_HOSHEN.includes(hoshen)) throw new Failure(Problem.unsupportedHoshen(hoshen));
  if (!root.strings.has("urim")) throw new Failure(Problem.missingKeysIn("", ["urim"]));
  urimGate(root);
  validate(LOCKFILE, root);
  const computed = integrityOf(root);
  if (root.strings.get("integrity") !== computed) throw new Failure(Problem.integrityMismatch(computed));
  lockfileRules(root);
  return `lockfile, hoshen ${hoshen}, urim ${PROTOCOL}`;
}

function contract(root: YamlMap): string {
  urimGate(root);
  validate(CONTRACT, root);
  contractRules(root);
  return `contract ${String(root.strings.get("contract"))}@${String(root.strings.get("version"))}, urim ${PROTOCOL}`;
}

function detail(text: string): string {
  const root = parseDocument(text);
  if (!isYamlMap(root)) throw new Failure(Problem.rootNotMapping);
  if (root.strings.has(RENAMED_KEY)) throw new Failure(Problem.renamedKey);
  if (root.strings.has("hoshen")) return lockfile(root, root.strings.get("hoshen") ?? null);
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
