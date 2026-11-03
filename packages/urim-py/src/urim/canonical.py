"""C: canonical JSON (sorted keys, no whitespace) + sha256. Byte-identical to urim-ts src/canonical.ts."""

from __future__ import annotations

import hashlib
from typing import Any

from .jsonfmt import canonical, js_units


def canonicalize(value: Any) -> str:
    return canonical(value)


def sha256(text: str) -> str:
    # Node's update(text, "utf8") writes a lone surrogate as U+FFFD; canonical output escapes them anyway.
    clean = "".join("\ufffd" if 0xD800 <= ord(c) <= 0xDFFF else c for c in js_units(text))
    return "sha256:" + hashlib.sha256(clean.encode("utf-8")).hexdigest()
