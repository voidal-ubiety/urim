"""RFC 8785 JSON Canonicalization of a checked document, and the lockfile integrity (SPEC §6.2).

Same as jcs.ts/jcs.rs; fixtures/jcs/corpus.json pins the bytes in all three ports.

Implements: C-098
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from decimal import Decimal

from urim.problem import NON_FINITE, Failure


def _number(x: float) -> str:
    """ECMAScript Number::toString of a finite double (RFC 8785 §3.2.2.3)."""
    if not math.isfinite(x):
        raise Failure(NON_FINITE)
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    # repr is the shortest round-tripping decimal; Decimal splits it into digits and an exponent.
    _, digit_tuple, exponent = Decimal(repr(abs(x))).normalize().as_tuple()
    digits = "".join(str(d) for d in digit_tuple)
    k = len(digits)
    n = k + int(exponent)  # the decimal point sits after n digits
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = f"{digits[:n]}.{digits[n:]}"
    elif -6 < n <= 0:
        body = "0." + "0" * -n + digits
    else:
        mantissa = digits if k == 1 else f"{digits[0]}.{digits[1:]}"
        body = f"{mantissa}e{'+' if n - 1 >= 0 else '-'}{abs(n - 1)}"
    return sign + body


def canonical(value: object) -> str:
    """Canonical JSON: keys sorted by UTF-16 code units, numbers as ECMAScript prints doubles."""
    if value is None or isinstance(value, (bool, str)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        # Integers become doubles, as I-JSON requires (RFC 8785 §3.2.2.3; SPEC §13 item 5 is open).
        return _number(float(value))
    if isinstance(value, dict):
        keys = sorted((str(k) for k in value), key=lambda k: k.encode("utf-16-be"))
        return (
            "{" + ",".join(f"{json.dumps(k, ensure_ascii=False)}:{canonical(value[k])}" for k in keys) + "}"
        )
    if isinstance(value, list):
        return "[" + ",".join(canonical(v) for v in value) + "]"
    raise TypeError(type(value).__name__)


def integrity_of(root: dict[str, object]) -> str:
    """``sha256-<base64>`` of the canonical form of ``root`` without its top-level ``integrity`` key."""
    body = canonical({k: v for k, v in root.items() if k != "integrity"})
    return "sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
