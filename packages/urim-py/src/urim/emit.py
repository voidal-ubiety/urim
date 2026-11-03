"""C: ``urim emit`` as a pure function. Definition -> canonical contract JSON + hash (same bytes as urim-ts)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .boundary import json_name, to_json
from .canonical import canonicalize, sha256
from .types import Definition


@dataclass(frozen=True)
class Emitted:
    document: Any
    json: str
    hash: str


def contract_document(d: Definition) -> dict[str, Any]:
    return {
        json_name("urim_contract"): 1,
        "contract": d.contract,
        "tiers": [
            {"id": t.id, "provider": t.provider, "model": t.model, "version": t.version, "camp": t.camp}
            for t in d.tiers
        ],
        "input": d.input.to_json_schema(),
        "questions": {
            name: {
                "type": q.type,
                "prompt": q.prompt,
                "options": [{"label": k, "description": v} for k, v in q.options.items()],
            }
            for name, q in d.questions.items()
        },
        "confidence": d.confidence,
        # JS Array.sort on ASCII strings == Python sorted
        "failover": {"on": sorted(d.failover_on)},
        "thresholds": {
            n: {"on": t.on, "default": t.default, "objective": to_json(t.objective)} for n, t in d.thresholds.items()
        },
        "hooks": {"prepare": d.prepare is not None, "interpret": d.interpret is not None},
    }


def emit(d: Definition) -> Emitted:
    doc = contract_document(d)
    text = canonicalize(doc)
    return Emitted(doc, text, sha256(text))
