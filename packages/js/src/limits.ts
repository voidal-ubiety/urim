// Hostile-input limits shared by every port; values must match limits.rs and limits.py.
// Listed in SECURITY.md.
// Implements: C-080, C-083

/** Largest accepted input in bytes (1 MiB); larger input is rejected before it is fully read. */
export const MAX_BYTES = 1_048_576;
/** Deepest accepted nesting of collections; the root mapping is depth 1. */
export const MAX_DEPTH = 64;
