"""C: pure fitting math for ``urim fit`` (design §6, D8), mirroring urim-ts src/fit-math.ts. No I/O.

Checked against vectors generated from the TS functions (shared-fixtures/fit.vectors.json), exact float equality.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .types import ABSENT, Objective


@dataclass(frozen=True)
class Scored:
    """One scored prediction on the threshold's question: portable confidence and whether value == label."""

    confidence: float | None
    correct: bool


@dataclass(frozen=True)
class CutoffFit:
    cutoff: float | None
    met: bool
    precision: float | None
    escalation: float | None


def _kept(xs: Sequence[Scored], c: float) -> list[Scored]:
    return [x for x in xs if x.confidence is not None and x.confidence >= c]


def precision_at(xs: Sequence[Scored], c: float) -> float | None:
    """Precision of answers that pass cutoff c; None when nothing passes."""
    k = _kept(xs, c)
    return None if not k else sum(1 for x in k if x.correct) / len(k)


def escalation_at(xs: Sequence[Scored], c: float) -> float:
    """Fraction escalated (below c, or no portable confidence)."""
    return 0 if not xs else (len(xs) - len(_kept(xs, c))) / len(xs)


def _candidates(xs: Sequence[Scored]) -> list[float]:
    return sorted({x.confidence for x in xs if x.confidence is not None})


def _precision_or_minus_one(xs: Sequence[Scored], c: float) -> float:
    v = precision_at(xs, c)
    return -1 if v is None else v


def fit_cutoff(xs: Sequence[Scored], objective: Objective) -> CutoffFit:
    """Candidates are the observed confidences.
    min_precision p: lowest cutoff whose precision >= p. escalation_rate r: highest cutoff whose escalation <= r.
    Both: the precision cut if it does not exceed the escalation cut; else unmet."""
    p = None if objective.min_precision is ABSENT else objective.min_precision
    r = None if objective.escalation_rate is ABSENT else objective.escalation_rate
    if p is None and r is None:
        return CutoffFit(None, True, None, None)
    cs = _candidates(xs)
    c_p = None if p is None else next((c for c in cs if _precision_or_minus_one(xs, c) >= p), None)
    c_e = None if r is None else next((c for c in reversed(cs) if escalation_at(xs, c) <= r), None)
    if (p is not None and c_p is None) or (r is not None and c_e is None):
        cutoff = None
    elif c_p is not None and c_e is not None:
        cutoff = c_p if c_p <= c_e else None
    else:
        cutoff = c_p if c_p is not None else c_e
    if cutoff is None:
        return CutoffFit(None, False, None, None)
    return CutoffFit(cutoff, True, precision_at(xs, cutoff), escalation_at(xs, cutoff))


def accuracy(xs: Sequence[Scored]) -> float:
    return 0 if not xs else sum(1 for x in xs if x.correct) / len(xs)


def brier(xs: Sequence[Scored]) -> float | None:
    """Brier score treating portable confidence as P(correct). Ignores None confidence; None when none."""
    s = [x for x in xs if x.confidence is not None]
    if not s:
        return None
    total = 0.0
    for x in s:  # left-to-right, like Array.reduce
        total += (x.confidence - (1 if x.correct else 0)) ** 2  # type: ignore[operator]
    return total / len(s)


def flip_rate(runs: Sequence[Sequence[str]]) -> float:
    """runs[r][i] = answer for case i on run r. Fraction of cases whose answer changed between runs."""
    n = len(runs[0]) if runs else 0
    if n == 0:
        return 0
    return sum(1 for i in range(n) if len({r[i] if i < len(r) else None for r in runs}) > 1) / n


def stdev(xs: Sequence[float]) -> float:
    """Population standard deviation."""
    if not xs:
        return 0
    m = 0.0
    for x in xs:
        m += x
    m /= len(xs)
    acc = 0.0
    for x in xs:
        acc += (x - m) ** 2
    return math.sqrt(acc / len(xs))


def percentile(xs: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile."""
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, math.ceil((p / 100) * len(s)) - 1))]
