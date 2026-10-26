"""String formats of the urim 0.2 type vocabulary (SPEC §5.1.2). Same as formats.ts/formats.rs.

The inputs are already ASCII (schema.py refuses non-ASCII first); the patterns use ASCII classes.

Implements: C-096
"""

from __future__ import annotations

import re

from urim.node import Fmt

_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}")
#: Proposed reserved ids (SPEC §5.1.2): they match the id pattern but are refused.
_RESERVED_IDS = ("constructor", "prototype")
_NUM = r"(?:0|[1-9][0-9]*)"
_PRE = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER_BODY = rf"{_NUM}\.{_NUM}\.{_NUM}(?:-{_PRE}(?:\.{_PRE})*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
_SEMVER = re.compile(_SEMVER_BODY)
_COMPARATOR = re.compile(rf"(?:>=|<=|>|<|=|\^|~)?{_SEMVER_BODY}")
_PROTOCOL = re.compile(rf"{_NUM}\.{_NUM}")
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
#: 32 bytes are 44 base64 characters: 42 free, one with its low two bits zero, then one ``=``.
_INTEGRITY = re.compile(r"sha256-[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=")
_TIMESTAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?"
    r"(?:[Zz]|[+-]([0-9]{2}):([0-9]{2}))"
)


def is_id(s: str) -> bool:
    """Return whether ``s`` is an id: a-z, then up to 63 of a-z, 0-9, ``_``, ``-``; not reserved."""
    return _ID.fullmatch(s) is not None and s not in _RESERVED_IDS


def _is_semver_range(s: str) -> bool:
    return all(
        part != "" and all(_COMPARATOR.fullmatch(c) for c in part.split(" ")) for part in s.split(" || ")
    )


def _days_in(year: int, month: int) -> int:
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month in (4, 6, 9, 11) else 31


def _is_timestamp(s: str) -> bool:
    m = _TIMESTAMP.fullmatch(s)
    if m is None:
        return False
    y, mo, d, h, mi, sec, oh, om = (int(x or "0") for x in m.groups())
    return (
        1 <= mo <= 12
        and 1 <= d <= _days_in(y, mo)
        and h <= 23
        and mi <= 59
        and sec <= 60
        and oh <= 23
        and om <= 59
    )


def matches(fmt: Fmt, s: str) -> bool:  # noqa: PLR0911 - one return per format reads best
    """Whether ``s`` (non-empty, ASCII) has format ``fmt``; ``string`` and ``expr`` accept any text."""
    if fmt in ("string", "expr"):
        return s != ""
    if fmt == "id":
        return is_id(s)
    if fmt == "target_id":
        parts = s.split("/")
        return len(parts) == 2 and all(is_id(p) for p in parts)
    if fmt == "capability_path":
        return all(is_id(p) for p in s.split("."))
    if fmt == "semver":
        return _SEMVER.fullmatch(s) is not None
    if fmt == "semver_range":
        return _is_semver_range(s)
    if fmt == "protocol_version":
        return _PROTOCOL.fullmatch(s) is not None
    if fmt == "hash":
        return _HASH.fullmatch(s) is not None
    if fmt == "integrity":
        return _INTEGRITY.fullmatch(s) is not None
    if fmt == "timestamp":
        return _is_timestamp(s)
    if fmt == "x_key":
        return s.startswith("x-") and is_id(s[2:])
    return s == "native" or (s.startswith("portable/") and is_id(s[len("portable/") :]))
