// The closed-schema interpreter: checks a value against a generated schema node (schema.gen.ts).
// Same algorithm as schema.rs/schema.py; CONTRACT.md C-095 states the order.
// Implements: C-095, C-096, C-097, C-088, C-092
import { hasInvisible, sanitize } from "./display.js";
import type { Fmt } from "./formats.js";
import { matches } from "./formats.js";
import type { Field, Leaf, Node } from "./node.js";
import { Failure, Problem } from "./problem.js";
import type { Value, YamlMap } from "./profile.js";
import { isYamlMap } from "./profile.js";
import { EXTENSION, FORMATS } from "./schema.gen.js";

/** A position in the document: mapping keys and sequence indexes from the root. */
export type Path = readonly (string | number)[];

const PLAIN = /^[A-Za-z0-9_./-]+$/;

/** `questions.team.options`, `targets["a b"]`, `levels[0]`; every key is sanitized (C-089). */
export function pathText(path: Path): string {
  let out = "";
  for (const seg of path) {
    if (typeof seg === "number") out += `[${seg}]`;
    else if (PLAIN.test(seg)) out += out === "" ? seg : `.${seg}`;
    else out += `["${sanitize(seg.replace(/\\/g, "\\\\").replace(/"/g, '\\"'))}"]`;
  }
  return out;
}

const fail = (message: string): never => {
  throw new Failure(message);
};
function mustBe(path: Path, desc: string): never {
  return fail(Problem.mustBe(pathText(path), desc));
}

/** The YAML kind a node accepts, for `alt` dispatch. */
type Kind = "string" | "number" | "boolean" | "mapping" | "sequence";
function kindOf(value: Value): Kind | null {
  if (typeof value === "string") return "string";
  if (typeof value === "bigint" || typeof value === "number") return "number";
  if (typeof value === "boolean") return "boolean";
  if (isYamlMap(value)) return "mapping";
  if (Array.isArray(value)) return "sequence";
  return null;
}
/** The YAML kind each schema leaf accepts; `alt` picks its option by this. A table, so every
 * leaf kind has an entry even though today's schema only puts some of them in an `alt`. */
const ACCEPTS: Readonly<Record<Leaf["k"], Kind>> = {
  str: "string",
  enum: "string",
  int: "number",
  num: "number",
  bool: "boolean",
  list: "sequence",
  map: "mapping",
  obj: "mapping",
  one: "mapping",
  opaque: "mapping",
};
function accepts(node: Leaf): Kind {
  return ACCEPTS[node.k];
}

/** Invisible characters (C-088), then non-ASCII (C-092): shared by values and keys. */
function asciiAndVisible(path: Path, s: string): void {
  if (hasInvisible(s)) fail(Problem.invisibleIn(pathText(path)));
  // Any UTF-16 code unit above 0x7F means a character above U+007F.
  if (s.split("").some((unit) => unit.charCodeAt(0) > 0x7f)) fail(Problem.nonAsciiIn(pathText(path)));
}

/** A string of format `fmt` at `path`: invisible (C-088), then non-ASCII (C-092), then the format. */
export function checkString(path: Path, value: Value, fmt: Fmt, desc: string): string {
  if (typeof value !== "string" || value === "") return mustBe(path, desc);
  if (fmt !== "string" && fmt !== "expr") asciiAndVisible(path, value);
  if (!matches(fmt, value)) mustBe(path, desc);
  return value;
}

function asMapping(path: Path, value: Value, desc: string): YamlMap {
  if (!isYamlMap(value)) return mustBe(path, desc);
  if (value.size !== value.strings.size) fail(Problem.nonStringKey(pathText(path)));
  return value;
}

function checkObject(node: Extract<Node, { k: "obj" }>, value: Value, path: Path): void {
  const map = asMapping(path, value, node.desc);
  let fields: readonly Field[] = node.fields;
  const others = new Map<string, string[]>();
  if (node.tag !== null) {
    const tag = node.tag;
    const tagValue = map.strings.get(tag.field);
    for (const f of node.fields)
      if (f.name === tag.field && tagValue !== undefined) check(f.node, tagValue, [...path, f.name]);
    for (const [variant, extra] of tag.variants) {
      if (tagValue === undefined || variant === tagValue) fields = [...fields, ...extra];
      else for (const f of extra) others.set(f.name, [...(others.get(f.name) ?? []), variant]);
    }
  }
  const known = new Set(fields.map((f) => f.name));
  for (const key of map.strings.keys()) {
    if (known.has(key)) continue;
    const at = [...path, key];
    const removed = node.removed.find(([k]) => k === key);
    if (removed !== undefined) fail(`${pathText(at)} ${removed[1]}`);
    const variants = others.get(key);
    if (variants !== undefined && node.tag !== null) {
      fail(Problem.onlyWhen(pathText(at), node.tag.field, variants));
    }
    if (node.ext && key.startsWith("x-")) checkExtensionKey(at, key);
    else fail(Problem.unknownKey(pathText(at)));
  }
  // Without a tag value only the shared fields are required; the missing tag is reported.
  const required = map.strings.has(node.tag?.field ?? "") ? fields : node.fields;
  const missing = required.filter((f) => f.req && !map.strings.has(f.name)).map((f) => f.name);
  if (missing.length > 0) fail(Problem.missingKeysIn(pathText(path), missing));
  for (const [key, child] of map.strings) {
    const field = fields.find((f) => f.name === key);
    if (field !== undefined) {
      if (field.name !== node.tag?.field) check(field.node, child, [...path, key]);
    } else check(EXTENSION, child, [...path, key]);
  }
}

/** An `x-<provider>` key at a position that allows one (SPEC §5.11.1, §5.11.2). */
function checkExtensionKey(path: Path, key: string): void {
  checkString(path, key, "x_key", FORMATS.x_key);
  if (key.startsWith("x-urim-")) fail(Problem.reservedExtension(pathText(path)));
}

function check(node: Node, value: Value, path: Path): void {
  switch (node.k) {
    case "str":
      checkString(path, value, node.fmt, node.desc);
      return;
    case "int":
      if (typeof value !== "bigint" || (node.min !== null && value < node.min)) mustBe(path, node.desc);
      return;
    case "num": {
      const n = typeof value === "bigint" ? Number(value) : value;
      if (typeof n !== "number" || !Number.isFinite(n)) mustBe(path, node.desc);
      const low = node.min === null || (node.minOpen ? n > node.min : n >= node.min);
      const high = node.max === null || (node.maxOpen ? n < node.max : n <= node.max);
      if (!low || !high) mustBe(path, node.desc);
      return;
    }
    case "bool":
      if (typeof value !== "boolean") mustBe(path, node.desc);
      return;
    case "enum":
      if (typeof value !== "string" || !node.values.includes(value)) mustBe(path, node.desc);
      return;
    case "list": {
      if (!Array.isArray(value) || value.length < node.min) mustBe(path, node.desc);
      const items: readonly Value[] = value;
      items.forEach((item, i) => {
        check(node.items, item, [...path, i]);
        const first = node.unique ? items.indexOf(item) : i;
        if (first !== i) fail(Problem.repeats(pathText([...path, i]), pathText([...path, first])));
      });
      return;
    }
    case "map": {
      const map = asMapping(path, value, node.desc);
      if (map.size < node.min) mustBe(path, node.desc);
      for (const [key, child] of map.strings) {
        const entry = node.entries.find((f) => f.name === key);
        if (entry !== undefined) check(entry.node, child, [...path, key]);
        else {
          checkKey([...path, key], key, node.key);
          check(node.value, child, [...path, key]);
        }
      }
      const missing = node.entries.filter((f) => f.req && !map.strings.has(f.name)).map((f) => f.name);
      if (missing.length > 0) fail(Problem.missingKeysIn(pathText(path), missing));
      return;
    }
    case "obj":
      checkObject(node, value, path);
      return;
    case "one": {
      const map = asMapping(path, value, node.desc);
      for (const key of map.strings.keys()) {
        const forbid = node.forbid.find(([k]) => k === key);
        if (forbid !== undefined) fail(`${pathText(path)} ${forbid[1]}`);
        if (!node.keys.some((f) => f.name === key)) fail(Problem.unknownKey(pathText([...path, key])));
      }
      if (map.strings.size !== 1) mustBe(path, node.desc);
      for (const f of node.keys) {
        const child = map.strings.get(f.name);
        if (child !== undefined) check(f.node, child, [...path, f.name]);
      }
      return;
    }
    case "alt": {
      const kind = kindOf(value);
      const option = node.options.find((o) => accepts(o) === kind);
      if (option === undefined) mustBe(path, node.desc);
      check(option, value, path);
      return;
    }
    case "opaque": {
      const map = asMapping(path, value, node.desc);
      if (map.size === 0) mustBe(path, node.desc);
      return;
    }
  }
}

/** A mapping key of format `fmt`: same order as a string value, with its own message. */
function checkKey(path: Path, key: string, fmt: Fmt): void {
  asciiAndVisible(path, key);
  if (!matches(fmt, key)) fail(Problem.badKey(pathText(path), FORMATS[fmt]));
  if (fmt === "x_key" && key.startsWith("x-urim-")) fail(Problem.reservedExtension(pathText(path)));
}

/** Check `value` (a document root) against `node`; throws `Failure` with the first problem. */
export function validate(node: Node, value: Value): void {
  check(node, value, []);
}
