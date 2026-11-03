"""C: the systemone body (TypeSafe reference; also Microsoft, Cloudflare, Liquid, Perplexity, Fastino, Inception).
Source: https://docs.typesafe.ai/api/system-one (checked 2026-10-28 EDT)."""

from __future__ import annotations

from typing import Any

from ..types import Definition, Question, Tier
from .shared import (
    Decoded,
    RawAnswer,
    argmax,
    binary_confidence,
    binary_label,
    nonconformant,
    num,
    score_labels,
    to_answers,
    vendor_confidence,
)

PATH = "/v1/systemone"


def _criteria(q: Question) -> Any:
    if q.type == "choice":
        return dict(q.options)
    if q.type == "score":
        return list(q.options.values())  # ordered; index = level from 0
    return {"true": q.options["yes"], "false": q.options["no"]}


def encode(d: Definition, wire_model: str, state: Any) -> Any:
    return {
        "model": wire_model,
        "state": state,
        "questions": {
            name: {"type": q.type, "instructions": q.prompt, "criteria": _criteria(q)}
            for name, q in d.questions.items()
        },
    }


def _decode_one(name: str, q: Question, a: Any, sentinel: bool) -> RawAnswer | None:
    if not isinstance(a, dict):
        return None
    if q.type == "noul":
        p = num(a.get("noul"))
        return None if p is None else RawAnswer(name, binary_label(p), binary_confidence(p), p, None, "urim_derived")
    if q.type == "choice":
        return RawAnswer(
            name, a.get("choice"), vendor_confidence(a, sentinel), a.get("choice"), a.get("confidence"), "native"
        )
    labels = score_labels(q)
    given = a.get("probabilities")
    probs: dict[str, Any] = given if isinstance(given, dict) else {}
    ps = [num(probs.get(str(i))) for i in range(len(labels))]
    vals = [-1.0 if p is None else p for p in ps]
    label = None if all(v < 0 for v in vals) else labels[argmax(vals)]
    return RawAnswer(name, label, vendor_confidence(a, sentinel), a.get("score"), a.get("confidence"), "native")


def decode(d: Definition, tier: Tier, body: Any, *, unavailable_sentinel: bool = False) -> Decoded:
    if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
        return nonconformant(tier, "response has no answers map")
    raws = {}
    for name, q in d.questions.items():
        raw = _decode_one(name, q, body["answers"].get(name), unavailable_sentinel)
        if raw is not None:
            raws[name] = raw
    return to_answers(d, tier, raws, body)
