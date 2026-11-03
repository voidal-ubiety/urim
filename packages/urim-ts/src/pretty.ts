// C: reviewable canonical JSON — sorted keys (via canonicalize), 2-space indent, trailing newline.
// Caveat: integer-like object keys would be reordered by JSON.parse; none of our documents use them.
import { canonicalize } from "./canonical.ts";
export const prettyCanonical = (value: unknown): string => `${JSON.stringify(JSON.parse(canonicalize(value)), null, 2)}\n`;
