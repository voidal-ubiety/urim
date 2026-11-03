"""C: HTTP outcome -> closed error type. Generic map plus per-vendor maps carried as descriptor data."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .descriptors import GENERIC_ERRORS, Descriptor, ErrorMap, header
from .errors import ErrorType
from .types import WireReply


def _error_code(body: Any) -> str | None:
    err = body.get("error") if isinstance(body, dict) else None
    code = err.get("code") if isinstance(err, dict) else None
    return code if isinstance(code, str) else None


def _by_map(m: ErrorMap, reply: WireReply) -> ErrorType | None:
    if 200 <= reply.status < 300:
        return None
    code = _error_code(reply.body)
    rule = next((r for r in m.by_code if r.status == reply.status), None)
    if rule is not None and code is not None and code in rule.codes:
        return rule.codes[code]
    if reply.status in m.by_status:
        return m.by_status[reply.status]
    return "provider_unavailable" if reply.status >= 500 else "invalid_request"


def _retry_after_ms(m: ErrorMap, reply: WireReply) -> int | None:
    """Retry-After as integer seconds -> ms. HTTP-date form is not parsed (TODO if a vendor documents it)."""
    if "retry-after" not in m.retry_headers:
        return None
    raw = header(reply.headers, "retry-after")
    try:
        secs = float(raw) if raw is not None else math.nan
    except ValueError:
        return None
    return int(secs * 1000) if math.isfinite(secs) and secs >= 0 else None


@dataclass(frozen=True)
class Classified:
    type: ErrorType | None
    retry_after_ms: int | None


def classify_reply(reply: WireReply) -> ErrorType | None:
    return _by_map(GENERIC_ERRORS, reply)


def classify_vendor_reply(d: Descriptor, reply: WireReply) -> Classified:
    return Classified(_by_map(d.errors, reply), _retry_after_ms(d.errors, reply))
