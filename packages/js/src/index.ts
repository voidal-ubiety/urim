// Public API of the `urim` package. Same surface as lib.rs and urim/__init__.py.
// Implements: C-070, C-071, C-072
export type { CheckResult } from "./check.js";
export { checkFile, checkText, SUPPORTED_HOSHEN } from "./check.js";
export { MAX_BYTES, MAX_DEPTH } from "./limits.js";
export const VERSION = "0.0.1";
