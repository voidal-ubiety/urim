"""C: resolve each named threshold for the tier that answered (D4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from .errors import UrimError
from .types import Answer, Cut, Definition, Lock, Threshold, Tier


def _cut_value(name: str, t: Threshold, tier: Tier, mode: str, lock: Lock | None) -> tuple[float | None, str]:
    locked = None if lock is None else lock.cuts.get(name, {}).get(tier.id)
    if locked is not None:
        return locked, "lock"
    if t.default is not None:
        return t.default, "default"
    if mode == "prod":
        raise UrimError("lock_violation", f'threshold "{name}" has no cutoff for {tier.id}', tier=tier.id)
    return None, "none"


def _passes(value: float | None, confidence: float | None) -> bool:
    if value is None:
        return True
    if confidence is None:
        return False  # missing confidence against a real cutoff escalates
    return confidence >= value


def resolve_cuts(
    d: Definition,
    tier: Tier,
    answers: Mapping[str, Answer],
    *,
    mode: Literal["dev", "prod"] = "dev",
    lock: Lock | None = None,
) -> dict[str, Cut]:
    out = {}
    for name, t in d.thresholds.items():
        value, source = _cut_value(name, t, tier, mode, lock)
        a = answers.get(t.on)
        conf = None if a is None else a.confidence
        out[name] = Cut(value, source, _passes(value, conf), conf)  # type: ignore[arg-type]
    return out
