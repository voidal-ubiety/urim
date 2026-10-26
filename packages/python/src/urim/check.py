"""`urim check`: validate a hoshen lockfile or a contract's top-level shape.

Behavior is specified in CONTRACT.md (repo root) and shared with check.rs and check.ts. Every
string that reaches the output line goes through ``sanitize`` (C-089).

Implements: C-003, C-006, C-040..C-046, C-050..C-057, C-060, C-070, C-071, C-088, C-089, C-093, C-094
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from urim.display import display_path, has_invisible, sanitize
from urim.problem import (
    HOSHEN_NEVER_RELEASED,
    HOSHEN_NOT_INTEGER,
    NOT_URIM,
    QUESTIONS_EMPTY,
    RENAMED_KEY,
    RENAMED_KEY_USED,
    ROOT_NOT_MAPPING,
    STATE_NOT_MAPPING,
    SUPPORTED_HOSHEN,
    Failure,
    invisible_in,
    missing_keys,
    non_ascii_in,
    not_a_string,
    unsupported_hoshen,
)
from urim.profile import parse_document
from urim.read import read_text

__all__ = ["SUPPORTED_HOSHEN", "CheckResult", "check_file", "check_text"]

CONTRACT_REQUIRED = ("contract", "version", "state", "questions")


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one check: ``line`` is the single line the CLI prints."""

    ok: bool
    line: str

    @property
    def exit_code(self) -> int:
        """Process exit code for this result: 0 when ok, 1 otherwise."""
        return 0 if self.ok else 1


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _identifier(root: dict[Any, Any], name: str) -> str:
    """Return identifier ``name``'s string; invisible (C-088), then non-ASCII (C-092), are refused."""
    value = root[name]
    if not isinstance(value, str):
        raise Failure(not_a_string(name))
    if has_invisible(value):
        raise Failure(invisible_in(name))
    if not value.isascii():
        raise Failure(non_ascii_in(name))
    return value


def _lockfile(root: dict[Any, Any]) -> str:
    hoshen = root["hoshen"]
    if not _is_int(hoshen):
        raise Failure(HOSHEN_NOT_INTEGER)
    if hoshen == 1:
        raise Failure(HOSHEN_NEVER_RELEASED)
    if hoshen not in SUPPORTED_HOSHEN:
        raise Failure(unsupported_hoshen(hoshen))
    if "urim" not in root:
        raise Failure(missing_keys(["urim"]))
    return f"lockfile, hoshen {hoshen}, urim {sanitize(_identifier(root, 'urim'))}"


def _contract(root: dict[Any, Any]) -> str:
    spec_version = _identifier(root, "urim")
    missing = [k for k in CONTRACT_REQUIRED if k not in root]
    if missing:
        raise Failure(missing_keys(missing))
    contract_id = _identifier(root, "contract")
    version = _identifier(root, "version")
    if not isinstance(root["state"], dict):
        raise Failure(STATE_NOT_MAPPING)
    if not isinstance(root["questions"], dict) or not root["questions"]:
        raise Failure(QUESTIONS_EMPTY)
    return f"contract {sanitize(contract_id)}@{sanitize(version)}, urim {sanitize(spec_version)}"


def _detail(text: str) -> str:
    root = parse_document(text)
    if not isinstance(root, dict):
        raise Failure(ROOT_NOT_MAPPING)
    if RENAMED_KEY in root:
        raise Failure(RENAMED_KEY_USED)
    if "hoshen" in root:
        return _lockfile(root)
    if "urim" in root:
        return _contract(root)
    raise Failure(NOT_URIM)


def _run(file: str, text_of: Callable[[], str]) -> CheckResult:
    shown = sanitize(display_path(file))
    try:
        return CheckResult(ok=True, line=f"{shown}: ok ({_detail(text_of())})")
    except Failure as failure:
        return CheckResult(ok=False, line=f"{shown}: error: {failure.problem}")


def check_text(file: str, text: str) -> CheckResult:
    """Check YAML ``text``; ``file`` is used only in the message."""
    return _run(file, lambda: text)


def check_file(path: str) -> CheckResult:
    """Read and check the file at ``path``; the message names ``path`` exactly as given."""
    return _run(path, lambda: read_text(path))
