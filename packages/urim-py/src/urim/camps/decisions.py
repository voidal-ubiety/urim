"""C: the OpenAI decisions body. Sources as in urim-ts src/camps/decisions.ts (checked 2026-10-28 EDT).
TODO(vendor-fact): OpenAI's confidence formula is undocumented; native choice/score confidence passes through."""

from __future__ import annotations

from typing import Any

from ..errors import UrimError
from ..types import Definition, Question, Tier
from .shared import (
    Decoded,
    DecodedFail,
    RawAnswer,
    argmax,
    binary_confidence,
    binary_label,
    nonconformant,
    num,
    to_answers,
    vendor_confidence,
)

PATH = "/v1/decisions"
_NATIVE_TYPE = {"noul": "predicate", "choice": "choice", "score": "score"}


def _encode_question(name: str, q: Question) -> dict[str, Any]:
    base: dict[str, Any] = {"type": _NATIVE_TYPE[q.type], "name": name, "instructions": q.prompt}
    if q.type == "choice":
        return {**base, "choices": [{"value": v, "description": t} for v, t in q.options.items()]}
    if q.type == "score":
        return {**base, "levels": [{"label": v, "description": t} for v, t in q.options.items()]}
    return base  # predicates carry no yes/no descriptions (O2; accepted 2026-10-28)


def encode(d: Definition, wire_model: str, input: Any) -> Any:
    return {
        "model": wire_model,
        # TODO(vendor-fact): exact message item wrapper is medium confidence.
        "input": [{"role": "user", "content": [{"type": "input_json", "data": input}]}],
        "questions": [_encode_question(n, q) for n, q in d.questions.items()],
    }


def _decode_one(name: str, a: dict[str, Any], sentinel: bool) -> RawAnswer | None:
    t = a.get("type")
    if t == "predicate":
        p = num(a.get("probability"))
        # OpenAI returns no predicate confidence: Urim derives |2p - 1| and says so (urim_derived).
        return None if p is None else RawAnswer(name, binary_label(p), binary_confidence(p), p, None, "urim_derived")
    if t == "choice":  # a boolean choice never equals a string label -> nonconformant later
        return RawAnswer(
            name, a.get("choice"), vendor_confidence(a, sentinel), a.get("choice"), a.get("confidence"), "native"
        )
    if t == "score":
        probs = (
            [p for p in a.get("probabilities", []) if isinstance(p, dict)]
            if isinstance(a.get("probabilities"), list)
            else []
        )
        top = probs[argmax([-1.0 if (x := num(p.get("probability"))) is None else x for p in probs])] if probs else None
        return RawAnswer(
            name,
            None if top is None else top.get("label"),
            vendor_confidence(a, sentinel),
            a.get("score"),
            a.get("confidence"),
            "native",
        )
    return None


def decode(d: Definition, tier: Tier, body: Any, *, unavailable_sentinel: bool = False) -> Decoded:
    if not isinstance(body, dict) or not isinstance(body.get("answers"), list):
        return nonconformant(tier, "response has no answers array")
    names = list(d.questions.keys())
    raws: dict[str, RawAnswer] = {}
    for i, a in enumerate(body["answers"]):
        if not isinstance(a, dict):
            continue
        name = a["name"] if isinstance(a.get("name"), str) else (names[i] if i < len(names) else None)
        if name is None or name not in d.questions:
            continue
        if a.get("type") == "refusal":
            return DecodedFail(UrimError("refused", f'{tier.id} refused question "{name}"', tier=tier.id))
        raw = _decode_one(name, a, unavailable_sentinel)
        if raw is not None:
            raws[name] = raw
    return to_answers(d, tier, raws, body)
