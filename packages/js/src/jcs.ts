// RFC 8785 JSON Canonicalization of a checked document, and the lockfile integrity (SPEC §6.2).
// Same as jcs.rs/jcs.py; fixtures/jcs/corpus.json pins the bytes in all three ports.
// Implements: C-098
import { createHash } from "node:crypto";
import { Failure, Problem } from "./problem.js";
import type { Value, YamlMap } from "./profile.js";
import { isYamlMap } from "./profile.js";

/** Canonical JSON: keys sorted by UTF-16 code units, numbers as ECMAScript prints doubles. */
export function canonical(value: Value): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  // Integers become doubles, as I-JSON requires (RFC 8785 §3.2.2.3; SPEC §13 item 5 is open).
  if (typeof value === "bigint") return canonical(Number(value));
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Failure(Problem.nonFinite);
    return String(value);
  }
  if (isYamlMap(value)) {
    // String `<` compares UTF-16 code units, the order RFC 8785 §3.2.3 requires; keys are distinct.
    const entries = [...value.strings].sort(([a], [b]) => (a < b ? -1 : 1));
    return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(",")}}`;
  }
  return `[${value.map(canonical).join(",")}]`;
}

/** `sha256-<base64>` of the canonical form of `value` without its top-level `integrity` key. */
export function integrityOf(root: YamlMap): string {
  const strings = new Map(root.strings);
  strings.delete("integrity");
  const body = canonical({ strings, size: strings.size });
  return `sha256-${createHash("sha256").update(body, "utf8").digest("base64")}`;
}
