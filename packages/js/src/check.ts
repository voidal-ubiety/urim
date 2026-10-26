// `urim check`: validate a hoshen lockfile or a contract's top-level shape.
// Behavior is specified in fixtures/README.md and shared with the Python and Rust ports.
import { readFileSync } from "node:fs";
import { isCollection, isPair, isScalar, parseAllDocuments, visit } from "yaml";
import type { Tags } from "yaml";

export const SUPPORTED_HOSHEN: readonly bigint[] = [1n];
const CONTRACT_REQUIRED = ["contract", "version", "state", "questions"] as const;
const NOT_URIM =
  "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'";

export interface CheckResult {
  ok: boolean;
  line: string;
  exitCode: 0 | 1;
}

type Mapping = Record<string, unknown>;

const fail = (file: string, problem: string): CheckResult => ({
  ok: false,
  line: `${file}: error: ${problem}`,
  exitCode: 1,
});
const pass = (file: string, detail: string): CheckResult => ({
  ok: true,
  line: `${file}: ok (${detail})`,
  exitCode: 0,
});

const isMapping = (v: unknown): v is Mapping =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const has = (m: Mapping, k: string): boolean => Object.prototype.hasOwnProperty.call(m, k);

class InvalidYaml extends Error {}

const INT_MIN = -(2n ** 63n);
const INT_MAX = 2n ** 64n - 1n;

// YAML 1.2 core schema, but decimal integers with leading zeros (e.g. `01`) stay strings,
// matching serde_norway. Keeps the three implementations identical.
const coreTags = (tags: Tags): Tags =>
  tags.map((t) =>
    typeof t === "object" && t.tag === "tag:yaml.org,2002:int" && !t.format && t.test
      ? { ...t, test: /^[-+]?(?:0|[1-9][0-9]*)$/ }
      : t,
  );

function parseSingleDocument(text: string): unknown {
  // YAML 1.2 core schema; integers as BigInt so `1.0` (a float) is distinguishable from `1`.
  const docs = parseAllDocuments(text, {
    version: "1.2",
    schema: "core",
    customTags: coreTags,
    intAsBigInt: true,
    uniqueKeys: true,
  });
  if (!Array.isArray(docs)) throw new InvalidYaml(); // EmptyStream: no documents
  if (docs.length === 0) return null;
  if (docs.length > 1) throw new InvalidYaml();
  const doc = docs[0];
  if (doc.errors.length > 0) throw new InvalidYaml();
  visit(doc, {
    Pair(_, pair) {
      if (isPair(pair) && isCollection(pair.key)) throw new InvalidYaml(); // keys must be scalars
    },
    Scalar(_, node) {
      if (isScalar(node) && typeof node.value === "bigint" && (node.value < INT_MIN || node.value > INT_MAX)) {
        throw new InvalidYaml(); // outside 64-bit range
      }
    },
  });
  return doc.toJS({ maxAliasCount: 100 });
}

export function checkText(file: string, text: string): CheckResult {
  if (text.startsWith("\uFEFF")) text = text.slice(1);
  let root: unknown;
  try {
    root = parseSingleDocument(text);
  } catch {
    return fail(file, "invalid YAML");
  }
  if (!isMapping(root)) return fail(file, "root must be a mapping");

  if (has(root, "hoshen")) {
    const hoshen = root.hoshen;
    if (typeof hoshen !== "bigint") return fail(file, "hoshen must be an integer");
    if (!SUPPORTED_HOSHEN.includes(hoshen)) {
      return fail(file, `unsupported hoshen version ${hoshen} (supported: ${SUPPORTED_HOSHEN.join(", ")})`);
    }
    if (!has(root, "urim")) return fail(file, "missing required key(s): urim");
    if (typeof root.urim !== "string") return fail(file, "urim must be a string");
    return pass(file, `lockfile, hoshen ${hoshen}, urim ${root.urim}`);
  }

  if (has(root, "dctp") || has(root, "urim")) {
    if (has(root, "dctp") && has(root, "urim")) return fail(file, "set only one of 'dctp' or 'urim'");
    const key = has(root, "dctp") ? "dctp" : "urim";
    if (typeof root[key] !== "string") return fail(file, `${key} must be a string`);
    const missing = CONTRACT_REQUIRED.filter((k) => !has(root as Mapping, k));
    if (missing.length > 0) return fail(file, `missing required key(s): ${missing.join(", ")}`);
    for (const k of ["contract", "version"]) {
      if (typeof root[k] !== "string") return fail(file, `${k} must be a string`);
    }
    if (!isMapping(root.state)) return fail(file, "state must be a mapping");
    if (!isMapping(root.questions) || Object.keys(root.questions).length === 0) {
      return fail(file, "questions must be a non-empty mapping");
    }
    return pass(file, `contract ${root.contract}@${root.version}, ${key} ${root[key]}`);
  }

  return fail(file, NOT_URIM);
}

export function checkFile(path: string): CheckResult {
  let data: Buffer;
  try {
    data = readFileSync(path);
  } catch {
    return fail(path, "cannot read file");
  }
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(data);
  } catch {
    return fail(path, "file is not valid UTF-8");
  }
  return checkText(path, text);
}
