// The Urim YAML profile: text to a root mapping, rejecting everything the profile forbids
// before any value is built. Same rules and order as profile.rs and profile.py:
// 1. size limit (C-080), then profile characters only (c-printable without NEL, LS, PS or a
//    non-leading U+FEFF) (C-082);
// 2. well-formedness, in stream order: nesting deeper than MAX_DEPTH (C-083) is reported if it
//    comes before the first syntax error, undefined alias or second document (C-020, C-022);
//    those are `invalid YAML`. The parser's own nesting-limit error is `too deep`;
// 3. profile violations, first in stream order: an anchor or alias (C-084), a tag (C-085), a
//    `<<` key (C-086), an invisible character in a key (C-087). Anchor beats tag on the same
//    node (C-090);
// 4. duplicate keys, collection keys, integers outside 64-bit range → invalid YAML (C-021,
//    C-023, C-024).
// Values are built into `Map`s, never plain objects, so keys like `__proto__` are inert (C-091).
// Implements: C-014, C-020..C-028, C-080, C-082..C-087, C-090, C-091
import type { Node, Tags } from "yaml";
import { isAlias, isMap, isScalar, isSeq, parseAllDocuments } from "yaml";
import { codePoints, hasInvisible, isProfileChar } from "./display.js";
import { MAX_BYTES, MAX_DEPTH } from "./limits.js";
import { Failure, Problem } from "./problem.js";

/** A YAML mapping: string keys only are addressable; `size` counts every key. */
export interface YamlMap {
  readonly strings: ReadonlyMap<string, Value>;
  readonly size: number;
}
export type Value = null | boolean | bigint | number | string | readonly Value[] | YamlMap;

export const isYamlMap = (v: Value | undefined): v is YamlMap =>
  typeof v === "object" && v !== null && !Array.isArray(v);

const INT_MIN = -(2n ** 63n);
const INT_MAX = 2n ** 64n - 1n;

// YAML 1.2 core schema, but decimal integers with leading zeros (e.g. `01`) stay strings,
// matching the other ports.
const coreTags = (tags: Tags): Tags =>
  tags.map((t) =>
    typeof t === "object" && t.tag === "tag:yaml.org,2002:int" && !t.format && t.test
      ? { ...t, test: /^[-+]?(?:0|[1-9][0-9]*)$/ }
      : t,
  );

interface Violation {
  readonly at: number;
  readonly problem: string;
}

interface Walk {
  /** First collection nested deeper than MAX_DEPTH (rule 2). */
  tooDeep?: Violation;
  /** First alias whose anchor is not defined earlier: a YAML error (rule 2). */
  undefinedAlias?: Violation;
  /** First profile violation (rule 3). */
  violation?: Violation;
  /** Some mapping has two equal keys (rule 4). */
  duplicate?: true;
}

/**
 * The identity of a scalar key for duplicate detection, matching the yaml package's own
 * `uniqueKeys` equality (scalar values compared with `===`) in O(1) per key instead of its
 * O(n) scan. NaN equals nothing, so it gets no identity; +0 and -0 share "number:0".
 */
function keyIdentity(key: Node): string | undefined {
  if (!isScalar(key)) return undefined; // collection keys are refused later (C-023)
  const value: unknown = key.value;
  if (typeof value === "number" && Number.isNaN(value)) return undefined;
  return `${typeof value}:${String(value)}`;
}

type Item = { readonly node: Node; readonly depth: number; readonly isKey: boolean };

/** The profile violation on one node itself, if any (rule 3). */
function nodeViolation(node: Node, isKey: boolean): string | undefined {
  if (isAlias(node) || node.anchor !== undefined) return Problem.anchorOrAlias;
  if (node.tag !== undefined) return Problem.tag;
  if (!isKey || !isScalar(node)) return undefined;
  if (node.value === "<<") return Problem.mergeKey;
  if (typeof node.value === "string" && hasInvisible(node.value)) return Problem.invisibleInKey;
  return undefined;
}

/** Walk the tree in document order with an explicit stack (no recursion on input depth). */
function walk(root: Node): Walk {
  const result: Walk = {};
  const anchors = new Set<string>();
  const stack: Item[] = [{ node: root, depth: 1, isKey: false }];
  while (stack.length > 0 && result.tooDeep === undefined) {
    const { node, depth, isKey } = stack.pop() as Item;
    const at = (node.range as [number, number, number])[0];
    if (node.anchor !== undefined) anchors.add(node.anchor);
    if (isAlias(node) && !anchors.has(node.source) && result.undefinedAlias === undefined) {
      result.undefinedAlias = { at, problem: Problem.invalidYaml };
    }
    const problem = nodeViolation(node, isKey);
    if (problem !== undefined && result.violation === undefined) result.violation = { at, problem };
    const children: Item[] = [];
    if (isMap(node)) {
      const seen = new Set<string>();
      for (const pair of node.items) {
        const id = keyIdentity(pair.key as Node);
        if (id !== undefined) {
          if (seen.has(id)) result.duplicate = true;
          seen.add(id);
        }
        children.push({ node: pair.key as Node, depth: depth + 1, isKey: true });
        if (pair.value) children.push({ node: pair.value as Node, depth: depth + 1, isKey: false });
      }
    } else if (isSeq(node)) {
      for (const item of node.items) children.push({ node: item as Node, depth: depth + 1, isKey: false });
    }
    if ((isMap(node) || isSeq(node)) && depth > MAX_DEPTH) {
      result.tooDeep = { at, problem: Problem.tooDeep };
    }
    // Push one by one: spreading a large collection as call arguments overflows V8's stack (bug B-8).
    for (const child of children.reverse()) stack.push(child);
  }
  return result;
}

/** Build the value; collection keys and out-of-range integers are invalid YAML (rule 3). */
function toValue(node: Node | null): Value {
  if (node === null) return null;
  if (isMap(node)) {
    const strings = new Map<string, Value>();
    for (const pair of node.items) {
      // The parser never produces a null key; a value is null for `? key` with no value.
      const key = pair.key as Node;
      if (!isScalar(key)) throw new Failure(Problem.invalidYaml);
      const k = toValue(key);
      const v = toValue(pair.value as Node | null);
      if (typeof k === "string") strings.set(k, v);
    }
    return { strings, size: node.items.length };
  }
  if (isSeq(node)) return node.items.map((item) => toValue(item as Node | null));
  const value = (node as { value: unknown }).value;
  if (typeof value === "bigint" && (value < INT_MIN || value > INT_MAX)) {
    throw new Failure(Problem.invalidYaml);
  }
  return value as Value;
}

/** Parse `text` as one Urim-profile document; the root may be any value (check.ts decides). */
export function parseDocument(text: string): Value {
  if (Buffer.byteLength(text, "utf8") > MAX_BYTES) throw new Failure(Problem.tooLarge);
  if (text.startsWith("\uFEFF")) text = text.slice(1);
  for (const cp of codePoints(text)) if (!isProfileChar(cp)) throw new Failure(Problem.invalidYaml);
  const docs = parseAllDocuments(text, {
    version: "1.2",
    schema: "core",
    customTags: coreTags,
    intAsBigInt: true,
    uniqueKeys: false, // checked in walk(): the package's own check is O(n^2) per mapping
    prettyErrors: false, // we use e.pos only; prettifying is O(n) per error, O(n^2) per flood
  });
  // An empty stream is an empty array (the `EmptyStream` type), which YAML reads as null.
  const [doc, ...rest] = docs;
  if (doc === undefined) return null;
  // Rule 2: depth against the first syntax problem, whichever comes first in the stream.
  const syntax: Violation[] = [];
  for (const d of docs) {
    for (const e of d.errors) {
      // Exhaustion is the parser's own nesting limit (~800 levels); depth 65 always comes first.
      if (e.code !== "RESOURCE_EXHAUSTION") syntax.push({ at: e.pos[0], problem: Problem.invalidYaml });
    }
  }
  const second = rest[0];
  if (second !== undefined) syntax.push({ at: second.range[0], problem: Problem.invalidYaml });
  const found = walk(doc.contents as Node); // never null: an empty document is a null scalar
  if (found.undefinedAlias !== undefined) syntax.push(found.undefinedAlias);
  const firstSyntax = syntax.sort((a, b) => a.at - b.at)[0];
  if (found.tooDeep !== undefined && (firstSyntax === undefined || found.tooDeep.at < firstSyntax.at)) {
    throw new Failure(Problem.tooDeep);
  }
  if (firstSyntax !== undefined) throw new Failure(Problem.invalidYaml);
  // Rule 3, then rule 4.
  if (found.violation !== undefined) throw new Failure(found.violation.problem);
  if (found.duplicate === true) throw new Failure(Problem.invalidYaml);
  // The only errors not yet handled are RESOURCE_EXHAUSTION, which needs ~800 levels, so
  // tooDeep (depth 65) has already been thrown for them.
  return toValue(doc.contents as Node);
}
