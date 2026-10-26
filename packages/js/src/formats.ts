// String formats of the urim 0.2 type vocabulary (SPEC §5.1.2). Same as formats.rs/formats.py.
// The inputs are already ASCII (schema.ts refuses non-ASCII first), so these regexes see ASCII only.
// Implements: C-096
export type Fmt =
  | "string"
  | "expr"
  | "id"
  | "target_id"
  | "capability_path"
  | "semver"
  | "semver_range"
  | "protocol_version"
  | "hash"
  | "integrity"
  | "timestamp"
  | "x_key"
  | "confidence_ref";

const ID = /^[a-z][a-z0-9_-]{0,63}$/;
// Proposed reserved ids (SPEC §5.1.2): they match ID but are refused. `__proto__` fails ID anyway.
const RESERVED_IDS: readonly string[] = ["constructor", "prototype"];
const NUM = "(?:0|[1-9][0-9]*)";
const PRE = "(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)";
const SEMVER_BODY = `${NUM}\\.${NUM}\\.${NUM}(?:-${PRE}(?:\\.${PRE})*)?(?:\\+[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?`;
const SEMVER = new RegExp(`^${SEMVER_BODY}$`);
const COMPARATOR = new RegExp(`^(?:>=|<=|>|<|=|\\^|~)?${SEMVER_BODY}$`);
const PROTOCOL = new RegExp(`^${NUM}\\.${NUM}$`);
const HASH = /^sha256:[0-9a-f]{64}$/;
// 32 bytes are 44 base64 characters: 42 free, one with its low two bits zero, then one `=`.
const INTEGRITY = /^sha256-[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=$/;
const TIMESTAMP =
  /^([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?(?:[Zz]|[+-]([0-9]{2}):([0-9]{2}))$/;

export const isId = (s: string): boolean => ID.test(s) && !RESERVED_IDS.includes(s);

/** `a b || c`: `||`-separated sets of space-separated comparators (`>=1.3.0`, `^1.3.0`). */
function isSemverRange(s: string): boolean {
  return s.split(" || ").every((set) => set !== "" && set.split(" ").every((c) => COMPARATOR.test(c)));
}

function daysIn(year: number, month: number): number {
  if (month === 2) return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

function isTimestamp(s: string): boolean {
  const m = TIMESTAMP.exec(s);
  if (m === null) return false;
  const [y, mo, d, h, mi, sec, oh, om] = m.slice(1).map((x) => (x === undefined ? 0 : Number(x))) as [
    number,
    number,
    number,
    number,
    number,
    number,
    number,
    number,
  ];
  return (
    mo >= 1 &&
    mo <= 12 &&
    d >= 1 &&
    d <= daysIn(y, mo) &&
    h <= 23 &&
    mi <= 59 &&
    sec <= 60 &&
    oh <= 23 &&
    om <= 59
  );
}

/** Whether `s` (non-empty, ASCII) has format `fmt`. `string` and `expr` accept any non-empty text. */
export function matches(fmt: Fmt, s: string): boolean {
  switch (fmt) {
    case "string":
    case "expr":
      return s !== "";
    case "id":
      return isId(s);
    case "target_id": {
      const parts = s.split("/");
      return parts.length === 2 && parts.every(isId);
    }
    case "capability_path":
      return s.split(".").every(isId);
    case "semver":
      return SEMVER.test(s);
    case "semver_range":
      return isSemverRange(s);
    case "protocol_version":
      return PROTOCOL.test(s);
    case "hash":
      return HASH.test(s);
    case "integrity":
      return INTEGRITY.test(s);
    case "timestamp":
      return isTimestamp(s);
    case "x_key":
      return s.startsWith("x-") && isId(s.slice(2));
    case "confidence_ref":
      return s === "native" || (s.startsWith("portable/") && isId(s.slice("portable/".length)));
  }
}
