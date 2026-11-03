"""C: helpers shared by the camp codecs: label-space checks, the binary confidence rule, usage."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from ..errors import UrimError
from ..types import Answer, ConfidenceSource, Definition, Question, Tier


@dataclass(frozen=True)
class RawAnswer:
    """A decoded native answer, already reduced to a candidate label."""

    name: str
    label: Any
    confidence: float | None
    native_value: Any
    native_confidence: Any
    confidence_source: ConfidenceSource


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int | float | None
    output_tokens: int | float | None


@dataclass(frozen=True)
class DecodedOk:
    answers: Mapping[str, Answer]
    usage: TokenUsage | None
    model: str | None
    ok: Literal[True] = True


@dataclass(frozen=True)
class DecodedFail:
    error: UrimError
    ok: Literal[False] = False


Decoded = DecodedOk | DecodedFail


def num(v: Any) -> float | int | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def vendor_confidence(a: Mapping[str, Any], unavailable_sentinel: bool) -> float | int | None:
    """A vendor confidence. With the sentinel flag, 0 plus present-but-empty probabilities is "unavailable" -> None."""
    c = num(a.get("confidence"))
    if not unavailable_sentinel or c != 0:
        return c
    p = a.get("probabilities")
    empty = isinstance(p, (list, dict)) and len(p) == 0
    return None if empty else c


def _unit(v: Any) -> float | int | None:
    n = num(v)
    return n if n is not None and 0 <= n <= 1 else None


def nonconformant(tier: Tier, message: str) -> DecodedFail:
    return DecodedFail(UrimError("nonconformant_response", message, tier=tier.id))


def binary_label(p: float) -> str:
    """P(yes) -> label. A tie (0.5) reads "yes"; its confidence is 0, so no threshold can pass on it."""
    return "yes" if p >= 0.5 else "no"


def binary_confidence(p: float) -> float:
    """TypeSafe's documented (p_max - 1/n)/(1 - 1/n), n = 2, i.e. |2p - 1|. https://docs.typesafe.ai/confidence.md
    Rounded to 12 dp exactly as urim-ts does (Math.round(x * 1e12) / 1e12; half rounds up)."""
    x = ((max(p, 1 - p) - 0.5) / 0.5) * 1e12
    return math.floor(x + 0.5) / 1e12


def argmax(ps: list[float]) -> int:
    """Index of the largest value; first wins on a tie."""
    best = 0
    for i, p in enumerate(ps):
        if p > ps[best]:
            best = i
    return best


def usage_of(body: Mapping[str, Any]) -> TokenUsage | None:
    u = body.get("usage")
    return TokenUsage(num(u.get("input_tokens")), num(u.get("output_tokens"))) if isinstance(u, dict) else None


def to_answers(d: Definition, tier: Tier, raws: Mapping[str, RawAnswer], body: Mapping[str, Any]) -> Decoded:
    """Checks every question is answered inside its label space; never alters native values."""
    answers: dict[str, Answer] = {}
    for name, q in d.questions.items():
        raw = raws.get(name)
        if raw is None:
            return nonconformant(tier, f'question "{name}" not answered')
        if not isinstance(raw.label, str) or raw.label not in q.options:
            return nonconformant(tier, f'question "{name}" answered outside its labels')
        conf = _unit(raw.confidence)
        answers[name] = Answer(
            raw.label,
            conf,
            None if conf is None else raw.confidence_source,
            confidence_formula=None
            if conf is None
            else ("typesafe_normalized" if raw.confidence_source == "urim_derived" else "vendor_unspecified"),
            native={"name": raw.name, "value": raw.native_value, "confidence": raw.native_confidence},
        )
    model = body.get("model")
    return DecodedOk(answers, usage_of(body), model if isinstance(model, str) else None)


def score_labels(q: Question) -> list[str]:
    return list(q.options.keys())
