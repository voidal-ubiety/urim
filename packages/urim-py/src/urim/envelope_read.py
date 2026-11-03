"""C: consumer-side reader for urim/1 (design §5.2/§5.5). Required members checked; unknown ones ignored."""

from __future__ import annotations

from typing import Any

from .boundary import json_name
from .errors import Issue

_SOURCES = (None, "native", "urim_derived")
_FORMULAS = (None, "typesafe_normalized", "vendor_unspecified")


def _num_or_none(v: Any) -> bool:
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))


def read_envelope(v: Any) -> tuple[bool, list[Issue]]:
    if not isinstance(v, dict):
        return False, [Issue("$", "envelope must be an object")]
    issues: list[Issue] = []

    def need(path: str, ok: bool, msg: str) -> None:
        if not ok:
            issues.append(Issue(path, msg))

    need("envelope", v.get("envelope") == "urim/1", "unsupported envelope version (this reader speaks urim/1)")
    c = v.get("contract")
    need(
        "contract",
        isinstance(c, dict) and isinstance(c.get("id"), str) and isinstance(c.get("hash"), str),
        "needs {id, hash}",
    )
    t = v.get("tier")
    need(
        "tier",
        isinstance(t, dict) and isinstance(t.get("id"), str) and t.get("role") in ("primary", "fallback"),
        "needs {id, role}",
    )
    a = v.get("answers")
    need(
        "answers",
        isinstance(a, dict)
        and all(
            isinstance(x, dict)
            and isinstance(x.get("value"), str)
            and _num_or_none(x.get("confidence"))
            and isinstance(x.get("native"), dict)
            and x.get(json_name("confidence_source")) in _SOURCES
            and x.get(json_name("confidence_formula")) in _FORMULAS
            for x in a.values()
        ),
        "each answer needs {value, confidence: number|null, native}"
        " and an optional confidence source: native|urim_derived|null"
        " and an optional confidence formula: typesafe_normalized|vendor_unspecified|null",
    )
    need("thresholds", isinstance(v.get("thresholds"), dict), "must be an object")
    need("fallback", v.get("fallback") is None or isinstance(v.get("fallback"), dict), "must be null or an object")
    need("attempts", isinstance(v.get("attempts"), list), "must be an array")
    need("usage", isinstance(v.get("usage"), dict), "must be an object")
    need(json_name("request_ids"), isinstance(v.get(json_name("request_ids")), dict), "must be an object")
    need("at", isinstance(v.get("at"), str), "must be an ISO string")
    return (not issues), issues
