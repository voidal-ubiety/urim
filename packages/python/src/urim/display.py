"""Character classes shared by the profile and by output sanitization (same as display.rs/.ts).

Implements: C-082, C-087, C-089
"""

from __future__ import annotations

import os


def is_printable(cp: int) -> bool:
    """YAML 1.2 ``c-printable``: the only characters a document may contain (C-082)."""
    return (
        cp in (0x09, 0x0A, 0x0D, 0x85)
        or 0x20 <= cp <= 0x7E
        or 0xA0 <= cp <= 0xD7FF
        or 0xE000 <= cp <= 0xFFFD
        or cp >= 0x10000
    )


def is_profile_char(cp: int) -> bool:
    """Characters a Urim-profile document may contain (C-082; resolves D-006 and D-007).

    ``c-printable`` minus U+FEFF (only one leading byte-order mark, stripped before this check)
    and minus NEL, LS and PS, which YAML 1.1 parsers treat as line breaks but YAML 1.2 does not.
    """
    return is_printable(cp) and cp not in (0x85, 0x2028, 0x2029, 0xFEFF)


def is_invisible(cp: int) -> bool:
    """Invisible formatting and bidi-control characters: refused in keys and identifiers."""
    return (
        cp in (0xAD, 0x61C, 0x180E, 0xFEFF)
        or 0x200B <= cp <= 0x200F
        or 0x202A <= cp <= 0x202E
        or 0x2060 <= cp <= 0x2064
        or 0x2066 <= cp <= 0x206F
        or 0xFFF9 <= cp <= 0xFFFB
        or 0xE0000 <= cp <= 0xE007F
    )


def has_invisible(s: str) -> bool:
    """Whether ``s`` contains an invisible or bidi-control character (C-087, C-088)."""
    return any(is_invisible(ord(c)) for c in s)


def _unsafe_for_output(cp: int) -> bool:
    return cp <= 0x1F or 0x7F <= cp <= 0x9F or 0xD800 <= cp <= 0xDFFF or is_invisible(cp)


def sanitize(s: str) -> str:
    r"""Escape unsafe characters as ``\u{XXXX}`` (uppercase hex, at least 4 digits) (C-089)."""
    return "".join(f"\\u{{{ord(c):04X}}}" if _unsafe_for_output(ord(c)) else c for c in s)


def display_path(path: str) -> str:
    """``path`` as shown in output: undecodable bytes become U+FFFD, as in the other ports."""
    return os.fsencode(path).decode("utf-8", "replace")
