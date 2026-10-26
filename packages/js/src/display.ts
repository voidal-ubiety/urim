// Character classes shared by the profile and by output sanitization (same as display.rs/.py).
// Implements: C-082, C-087, C-089

/** YAML 1.2 `c-printable`: the only characters a document may contain (C-082). */
export function isPrintable(cp: number): boolean {
  return (
    cp === 0x09 ||
    cp === 0x0a ||
    cp === 0x0d ||
    (cp >= 0x20 && cp <= 0x7e) ||
    cp === 0x85 ||
    (cp >= 0xa0 && cp <= 0xd7ff) ||
    (cp >= 0xe000 && cp <= 0xfffd) ||
    cp >= 0x10000
  );
}

/**
 * Characters a Urim-profile document may contain: `c-printable` minus U+FEFF (only one leading
 * byte-order mark, stripped before this check) and minus NEL, LS and PS, which YAML 1.1 parsers
 * treat as line breaks but YAML 1.2 does not (C-082; resolves D-006 and D-007).
 */
export const isProfileChar = (cp: number): boolean =>
  isPrintable(cp) && cp !== 0x85 && cp !== 0x2028 && cp !== 0x2029 && cp !== 0xfeff;

/** Invisible formatting and bidi-control characters: refused in keys and identifiers (C-087, C-088). */
export function isInvisible(cp: number): boolean {
  return (
    cp === 0xad ||
    cp === 0x61c ||
    cp === 0x180e ||
    (cp >= 0x200b && cp <= 0x200f) ||
    (cp >= 0x202a && cp <= 0x202e) ||
    (cp >= 0x2060 && cp <= 0x2064) ||
    (cp >= 0x2066 && cp <= 0x206f) ||
    cp === 0xfeff ||
    (cp >= 0xfff9 && cp <= 0xfffb) ||
    (cp >= 0xe0000 && cp <= 0xe007f)
  );
}

/** Code points of `s`; a lone surrogate is reported as itself. */
export function* codePoints(s: string): Generator<number> {
  for (const ch of s) yield ch.codePointAt(0) as number;
}

export const hasInvisible = (s: string): boolean => {
  for (const cp of codePoints(s)) if (isInvisible(cp)) return true;
  return false;
};

/** C0, DEL, C1, invisible characters and lone surrogates must not reach a terminal unescaped. */
const unsafeForOutput = (cp: number): boolean =>
  cp <= 0x1f || (cp >= 0x7f && cp <= 0x9f) || (cp >= 0xd800 && cp <= 0xdfff) || isInvisible(cp);

/** Escape unsafe characters as `\u{XXXX}` (uppercase hex, at least 4 digits) (C-089). */
export function sanitize(s: string): string {
  let out = "";
  for (const cp of codePoints(s)) {
    out += unsafeForOutput(cp)
      ? `\\u{${cp.toString(16).toUpperCase().padStart(4, "0")}}`
      : String.fromCodePoint(cp);
  }
  return out;
}
