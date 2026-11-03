// C: canonical JSON (sorted keys, no whitespace) + sha256. Close to RFC 8785 JCS for the values we emit
// (strings, finite numbers, booleans, null). UNVERIFIED: full JCS number formatting for exotic floats.
import { createHash } from "node:crypto";

const encode = (value: unknown, path: string): string | undefined => {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError(`canonicalize: non-finite number at ${path}`);
    return JSON.stringify(value);
  }
  if (value === undefined) return undefined;
  if (Array.isArray(value)) return `[${value.map((v, i) => encode(v, `${path}[${i}]`) ?? "null").join(",")}]`;
  if (typeof value === "object") {
    const members = Object.keys(value).sort()
      .map((k) => [k, encode((value as Record<string, unknown>)[k], `${path}.${k}`)] as const)
      .filter((m): m is readonly [string, string] => m[1] !== undefined)
      .map(([k, v]) => `${JSON.stringify(k)}:${v}`);
    return `{${members.join(",")}}`;
  }
  throw new TypeError(`canonicalize: ${typeof value} is not JSON at ${path}`);
};

export const canonicalize = (value: unknown): string => encode(value, "$") ?? "null";
export const sha256 = (text: string): string => `sha256:${createHash("sha256").update(text, "utf8").digest("hex")}`;
