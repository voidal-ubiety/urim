"""C: JSON text exactly as ECMAScript JSON.stringify writes it, so both ports emit byte-identical bytes.

- Numbers follow ECMAScript Number::toString (shortest round-trip digits; ``1.0 -> "1"``, ``1e21 -> "1e+21"``,
  ``1e-7 -> "1e-7"``, ``-0.0 -> "0"``). Python's repr is also shortest round-trip; UNVERIFIED for any rare case
  where the two pick different shortest digit strings (none known).
- Strings escape only ``"``, ``\\``, control characters and lone surrogates, like JSON.stringify.
- ``canonical`` sorts object keys by UTF-16 code units (JavaScript ``Array.prototype.sort`` order).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

_SHORT = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def js_units(s: str) -> str:
    """Treat a Python str as JS does (UTF-16): an adjacent high+low surrogate pair is one astral character."""
    if not any(0xD800 <= ord(c) <= 0xDFFF for c in s):
        return s
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def js_string(s: str) -> str:
    out = []
    for ch in js_units(s):
        c = ord(ch)
        if ch in _SHORT:
            out.append(_SHORT[ch])
        elif c < 0x20 or 0xD800 <= c <= 0xDFFF:  # Python str holds lone surrogates as single code points
            out.append(f"\\u{c:04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def js_number(x: int | float, path: str = "$") -> str:
    if isinstance(x, bool):
        raise TypeError(f"bool is not a number at {path}")
    f = float(x)
    if not math.isfinite(f):
        raise TypeError(f"canonicalize: non-finite number at {path}")
    if f == 0:
        return "0"
    if isinstance(x, int) and abs(x) < 2**53:
        return str(x)
    sign = "-" if f < 0 else ""
    t = Decimal(repr(abs(f))).normalize().as_tuple()
    digits = "".join(map(str, t.digits))
    k = len(digits)
    n = int(t.exponent) + k
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        exp = ("+" if e >= 0 else "-") + str(abs(e))
        body = (digits if k == 1 else digits[0] + "." + digits[1:]) + "e" + exp
    return sign + body


def _utf16_key(k: str) -> bytes:
    return k.encode("utf-16-be", "surrogatepass")


def _wrap(open_: str, close: str, items: list[str], indent: str, step: str) -> str:
    """JSON.stringify layout: compact without ``step``; else one item per line, ``[]``/``{}`` when empty."""
    if not step or not items:
        return open_ + ",".join(items) + close
    inner = indent + step
    return open_ + "\n" + inner + (",\n" + inner).join(items) + "\n" + indent + close


def _encode(v: Any, path: str, sort: bool, indent: str = "", step: str = "") -> str | None:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return js_string(v)
    if isinstance(v, (int, float)):
        return js_number(v, path)
    if isinstance(v, (list, tuple)):
        deeper = indent + step
        return _wrap(
            "[", "]", [_encode(x, f"{path}[{i}]", sort, deeper, step) or "null" for i, x in enumerate(v)], indent, step
        )
    if isinstance(v, Mapping):
        keys = sorted(v.keys(), key=_utf16_key) if sort else list(v.keys())
        members = []
        for k in keys:
            if not isinstance(k, str):
                raise TypeError(f"canonicalize: non-string key at {path}")
            enc = _encode(v[k], f"{path}.{k}", sort, indent + step, step)
            if enc is not None:
                members.append(js_string(k) + (": " if step else ":") + enc)
        return _wrap("{", "}", members, indent, step)
    raise TypeError(f"canonicalize: {type(v).__name__} is not JSON at {path}")


def stringify(v: Any) -> str:
    """JSON.stringify(v) with insertion order (used for the pre-call token estimate)."""
    return _encode(v, "$", False) or "null"


def canonical(v: Any) -> str:
    return _encode(v, "$", True) or "null"


def pretty_canonical(v: Any) -> str:
    """urim-ts prettyCanonical: sorted keys, JSON.stringify(_, null, 2) layout, trailing newline."""
    return (_encode(v, "$", True, "", "  ") or "null") + "\n"
