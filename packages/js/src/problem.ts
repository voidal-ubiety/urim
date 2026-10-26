// Failure messages: the exact wording from CONTRACT.md, shared with problem.rs and problem.py.
// Implements: the message of every C-xxx failure (C-010..C-088)
import { MAX_BYTES, MAX_DEPTH } from "./limits.js";

export const SUPPORTED_HOSHEN: readonly bigint[] = [1n];

export const Problem = {
  cannotRead: "cannot read file",
  notRegularFile: "not a regular file",
  tooLarge: `file too large (max ${MAX_BYTES} bytes)`,
  notUtf8: "file is not valid UTF-8",
  invalidYaml: "invalid YAML",
  tooDeep: `nesting too deep (max depth ${MAX_DEPTH})`,
  anchorOrAlias: "anchors and aliases are not allowed",
  tag: "tags are not allowed",
  mergeKey: "merge keys (<<) are not allowed",
  invisibleInKey: "invisible or bidirectional control character in a mapping key",
  invisibleIn: (key: string) => `invisible or bidirectional control character in ${key}`,
  rootNotMapping: "root must be a mapping",
  hoshenNotInteger: "hoshen must be an integer",
  unsupportedHoshen: (v: bigint) =>
    `unsupported hoshen version ${v} (supported: ${SUPPORTED_HOSHEN.join(", ")})`,
  missingKeys: (keys: readonly string[]) => `missing required key(s): ${keys.join(", ")}`,
  notAString: (key: string) => `${key} must be a string`,
  bothSpecKeys: "set only one of 'dctp' or 'urim'",
  stateNotMapping: "state must be a mapping",
  questionsEmpty: "questions must be a non-empty mapping",
  notUrim: "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'",
} as const;

/** A failure carrying its message; thrown inside the pipeline, caught in check.ts. */
export class Failure extends Error {}
