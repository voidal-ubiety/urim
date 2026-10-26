"""Hostile-input limits shared by every port; values must match limits.rs and limits.ts.

Implements: C-080, C-083
"""

MAX_BYTES = 1_048_576
"""Largest accepted input in bytes (1 MiB); larger input is rejected before it is fully read."""

MAX_DEPTH = 64
"""Deepest accepted nesting of collections; the root mapping is depth 1."""
