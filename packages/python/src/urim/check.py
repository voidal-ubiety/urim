"""`urim check`: validate a hoshen 2 lockfile or a urim 0.2 contract.

Behavior is specified in CONTRACT.md (repo root) and shared with check.rs and check.ts. Every
string that reaches the output line goes through ``sanitize`` (C-089).

Implements: C-003, C-006, C-040, C-041, C-042, C-060, C-070, C-071, C-088, C-089, C-093..C-099
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from urim.display import display_path, sanitize
from urim.jcs import integrity_of
from urim.problem import (
    HOSHEN_NEVER_RELEASED,
    HOSHEN_NOT_INTEGER,
    NOT_URIM,
    RENAMED_KEY,
    RENAMED_KEY_USED,
    ROOT_NOT_MAPPING,
    SUPPORTED_HOSHEN,
    Failure,
    integrity_mismatch,
    missing_keys_in,
    unsupported_hoshen,
    unsupported_urim,
)
from urim.profile import parse_document
from urim.read import read_text
from urim.rules import contract_rules, lockfile_rules
from urim.schema import check_string, validate
from urim.schema_gen import CONTRACT, FORMATS, LOCKFILE, PROTOCOL

__all__ = ["SUPPORTED_HOSHEN", "CheckResult", "check_file", "check_text"]


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one check: ``line`` is the single line the CLI prints."""

    ok: bool
    line: str

    @property
    def exit_code(self) -> int:
        """Process exit code for this result: 0 when ok, 1 otherwise."""
        return 0 if self.ok else 1


def _urim_gate(root: dict[str, object]) -> None:
    """Apply the ``urim`` gate (SPEC §5.1.1): a protocol version, then exactly the supported one."""
    value = check_string(("urim",), root.get("urim"), "protocol_version", FORMATS["protocol_version"])
    if value != PROTOCOL:
        raise Failure(unsupported_urim(value))


def _string_keyed(root: dict[Any, Any]) -> dict[str, object]:
    return {k: v for k, v in root.items() if isinstance(k, str)}


def _lockfile(document: dict[Any, Any]) -> str:
    hoshen = document["hoshen"]
    if not isinstance(hoshen, int) or isinstance(hoshen, bool):
        raise Failure(HOSHEN_NOT_INTEGER)
    if hoshen == 1:
        raise Failure(HOSHEN_NEVER_RELEASED)
    if hoshen not in SUPPORTED_HOSHEN:
        raise Failure(unsupported_hoshen(hoshen))
    if "urim" not in document:
        raise Failure(missing_keys_in("", ["urim"]))
    root = _string_keyed(document)
    _urim_gate(root)
    validate(LOCKFILE, document)
    computed = integrity_of(root)
    if root["integrity"] != computed:
        raise Failure(integrity_mismatch(computed))
    lockfile_rules(root)
    return f"lockfile, hoshen {hoshen}, urim {PROTOCOL}"


def _contract(document: dict[Any, Any]) -> str:
    root = _string_keyed(document)
    _urim_gate(root)
    validate(CONTRACT, document)
    contract_rules(root)
    return f"contract {root['contract']}@{root['version']}, urim {PROTOCOL}"


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
