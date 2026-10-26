"""Failure messages: the exact wording from CONTRACT.md, shared with problem.rs and problem.ts.

Implements: the message of every C-xxx failure (C-010..C-099)
"""

from __future__ import annotations

from urim.limits import MAX_BYTES, MAX_DEPTH
from urim.schema_gen import PROTOCOL

SUPPORTED_HOSHEN = frozenset({2})

#: The pre-0.1 name of the ``urim`` key (C-093). Rejected, never read as an alias.
RENAMED_KEY = "dctp"

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
HOSHEN_NEVER_RELEASED = "hoshen 1 was never released; the first lockfile format is hoshen 2"
RENAMED_KEY_USED = f"the {RENAMED_KEY}: key was renamed to urim: before 0.1; replace it"
NON_FINITE = "a number that is not finite has no canonical JSON form"
NOT_URIM = "not a urim document: expected a lockfile with 'hoshen' or a contract with 'urim'"


def invisible_in(key: str) -> str:
    """C-088: an invisible character in identifier ``key``."""
    return f"invisible or bidirectional control character in {key}"


def non_ascii_in(key: str) -> str:
    """C-092: a non-ASCII (for example look-alike) character in identifier ``key``."""
    return f"non-ASCII character in {key}"


def unsupported_hoshen(value: int) -> str:
    """C-042: a hoshen integer outside SUPPORTED_HOSHEN."""
    supported = ", ".join(str(v) for v in sorted(SUPPORTED_HOSHEN))
    return f"unsupported hoshen version {value} (supported: {supported})"


def missing_keys_in(path: str, keys: list[str]) -> str:
    """Report the required keys that are absent, in schema order; ``path`` is empty at the root."""
    where = f" in {path}" if path else ""
    return f"missing required key(s){where}: " + ", ".join(keys)


def must_be(path: str, desc: str) -> str:
    """C-096: a value of the wrong type, format or range."""
    return f"{path} must be {desc}"


def unknown_key(path: str) -> str:
    """C-095: a key the closed schema does not define."""
    return f"unknown key {path}"


def non_string_key(path: str) -> str:
    """C-095: a mapping with a key that is not a string."""
    return f"{path or 'the root mapping'} has a non-string key"


def bad_key(path: str, desc: str) -> str:
    """C-096: a mapping key of the wrong format."""
    return f"key {path} must be {desc}"


def only_when(path: str, field: str, values: list[str]) -> str:
    """C-095: a key that belongs to another variant of a tagged mapping."""
    return f"{path} is only allowed when {field} is " + " or ".join(values)


def repeats(path: str, first: str) -> str:
    """C-096: a repeated item in a list that must not repeat."""
    return f"{path} repeats {first}"


def reserved_extension(path: str) -> str:
    """C-095: an extension key with the reserved ``x-urim-`` prefix."""
    return f"{path} uses the reserved prefix x-urim- (SPEC §5.11.2)"


def unsupported_urim(value: str) -> str:
    """C-041: a protocol version other than the one this checker supports."""
    return f"unsupported urim version {value} (supported: {PROTOCOL})"


def integrity_mismatch(computed: str) -> str:
    """C-098: the lockfile integrity is not the hash of its content."""
    return f"integrity does not match the file's content (computed {computed})"


def undeclared_experimental(path: str, kind: str) -> str:
    """C-097: an experimental question type that requires/prefers do not declare."""
    return f"{path} has experimental type {kind}: declare question_types.{kind} in requires or prefers"


def unknown_question(path: str, name: str) -> str:
    """C-097: a reference to a question the contract does not declare."""
    return f"{path} names no declared question: {name}"


def not_an_answer(path: str, question: str) -> str:
    """C-097: a policy ``when.answer`` that the question cannot give."""
    return f"{path} is not an answer of question {question}"


def also_preferred(path: str) -> str:
    """C-097: a capability in both requires and prefers."""
    return f"{path} is also in prefers; a capability is required or preferred, not both"


def no_emulation(path: str, name: str) -> str:
    """C-097: a fallback naming an emulation that is not registered."""
    return f"{path} names no registered emulation: {name}"


def not_a_target(path: str, value: str, targets: str) -> str:
    """C-099: an active or standby target that is not in the contract's targets."""
    return f"{path} is not a key of {targets}: {value}"


class Failure(Exception):  # noqa: N818 - a result, not an error condition of the program
    """A check failure carrying its message; raised inside the pipeline, caught in check.py."""

    def __init__(self, problem: str) -> None:
        """Carry ``problem``, the exact message line suffix."""
        super().__init__(problem)
        self.problem = problem
