"""Failure messages: the exact wording from CONTRACT.md, shared with problem.rs and problem.ts.

Implements: the message of every C-xxx failure (C-010..C-088)
"""

from __future__ import annotations

from urim.limits import MAX_BYTES, MAX_DEPTH

SUPPORTED_HOSHEN = frozenset({1})

CANNOT_READ = "cannot read file"
NOT_REGULAR_FILE = "not a regular file"
TOO_LARGE = f"file too large (max {MAX_BYTES} bytes)"
NOT_UTF8 = "file is not valid UTF-8"
INVALID_YAML = "invalid YAML"
TOO_DEEP = f"nesting too deep (max depth {MAX_DEPTH})"
ANCHOR_OR_ALIAS = "anchors and aliases are not allowed"
TAG = "tags are not allowed"
MERGE_KEY = "merge keys (<<) are not allowed"
INVISIBLE_IN_KEY = "invisible or bidirectional control character in a mapping key"
ROOT_NOT_MAPPING = "root must be a mapping"
HOSHEN_NOT_INTEGER = "hoshen must be an integer"
BOTH_SPEC_KEYS = "set only one of 'dctp' or 'urim'"
STATE_NOT_MAPPING = "state must be a mapping"
QUESTIONS_EMPTY = "questions must be a non-empty mapping"
NOT_URIM = "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'"


def invisible_in(key: str) -> str:
    """C-088: an invisible character in identifier ``key``."""
    return f"invisible or bidirectional control character in {key}"


def unsupported_hoshen(value: int) -> str:
    """C-042: a hoshen integer outside SUPPORTED_HOSHEN."""
    supported = ", ".join(str(v) for v in sorted(SUPPORTED_HOSHEN))
    return f"unsupported hoshen version {value} (supported: {supported})"


def missing_keys(keys: list[str]) -> str:
    """C-043/C-052: the required keys that are absent, in contract order."""
    return "missing required key(s): " + ", ".join(keys)


def not_a_string(key: str) -> str:
    """C-044/C-051/C-053: identifier ``key`` holds a non-string value."""
    return f"{key} must be a string"


class Failure(Exception):  # noqa: N818 - a result, not an error condition of the program
    """A check failure carrying its message; raised inside the pipeline, caught in check.py."""

    def __init__(self, problem: str) -> None:
        """Carry ``problem``, the exact message line suffix."""
        super().__init__(problem)
        self.problem = problem
