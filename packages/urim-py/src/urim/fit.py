"""A (thin) over C: the ``urim fit`` runner, mirroring urim-ts src/fit.ts. Calls each tier on a labelled eval set
through ``create_client`` with the adapters it is given, then hands scored data to the pure math in fit_math."""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from .boundary import to_json
from .canonical import canonicalize, sha256
from .client import _iso, _now_ms, create_client
from .emit import emit
from .fit_math import CutoffFit, Scored, accuracy, brier, fit_cutoff, flip_rate, percentile, stdev
from .testing import Adapter
from .types import ABSENT, ContractRef, Definition, EvalProvenance, Lock, LockTier, PriceTable


@dataclass(frozen=True)
class EvalCase:
    input: Any
    labels: Mapping[str, str]


@dataclass(frozen=True)
class CostEstimate:
    per_tier: Mapping[str, float]
    total: float | None
    currency: str | None
    unknown: tuple[str, ...]


@dataclass(frozen=True)
class QuestionReport:  # field order = urim-ts insertion order (the --report JSON is compared byte for byte)
    accuracy: float
    brier: float | None
    flip_rate: float


@dataclass(frozen=True)
class LatencyReport:
    p50: float | None
    p95: float | None


@dataclass(frozen=True)
class FitCost:
    amount: float
    currency: str


@dataclass(frozen=True)
class TierReport:
    questions: Mapping[str, QuestionReport]
    cutoffs: Mapping[str, CutoffFit]
    accuracy_stdev: float
    latency_ms: LatencyReport
    cost: FitCost | None
    failures: int


@dataclass(frozen=True)
class FitReport:
    contract: str
    n: int
    repeat: int
    tiers: Mapping[str, TierReport]


@dataclass(frozen=True)
class NeedsConfirmation:
    estimate: CostEstimate
    status: Literal["needs_confirmation"] = "needs_confirmation"


@dataclass(frozen=True)
class FitOk:
    lock: Lock
    report: FitReport
    estimate: CostEstimate
    set_hash: str
    status: Literal["ok"] = "ok"


@dataclass(frozen=True)
class ObjectivesUnmet:
    unmet: tuple[str, ...]
    report: FitReport
    estimate: CostEstimate
    set_hash: str
    status: Literal["objectives_unmet"] = "objectives_unmet"


FitOutcome = NeedsConfirmation | FitOk | ObjectivesUnmet


def _round(x: float) -> float:
    """Math.round(x * 1e9) / 1e9 (half rounds up, unlike Python's round)."""
    return math.floor(x * 1e9 + 0.5) / 1e9


def parse_cases(jsonl: str) -> list[EvalCase]:
    """JSONL eval set -> cases. Each line: {"input": ..., "labels": {question: label}}."""
    out = []
    for i, line in enumerate(ln for ln in jsonl.split("\n") if ln.strip()):
        v = json.loads(line)
        if not isinstance(v, dict) or "input" not in v or not isinstance(v.get("labels"), (dict, list)):
            raise ValueError(f"eval line {i + 1}: needs {{input, labels}}")
        out.append(EvalCase(v["input"], v["labels"]))
    return out


def estimate_fit_cost(d: Definition, n: int, repeat: int, prices: PriceTable | None) -> CostEstimate:
    """cases x repeat x per-call price. Token-priced and unpriced tiers are listed as unknown, never guessed."""
    per_tier: dict[str, float] = {}
    unknown: list[str] = []
    currency = None
    for t in d.tiers:
        e = None if prices is None else prices.entries.get(t.id)
        if e is None or e.per_call is ABSENT:
            unknown.append(t.id)
            continue
        per_tier[t.id] = _round(e.per_call * n * repeat)
        currency = currency or e.currency
    total = None if unknown else _round(sum(per_tier.values()))
    return CostEstimate(MappingProxyType(per_tier), total, currency, tuple(unknown))


def _or_failed(v: str | None) -> str:
    return "<failed>" if v is None else v


@dataclass(frozen=True)
class _Row:
    answers: Mapping[str, Any] | None  # Answer by question, None on failure
    latency: float
    cost: float | None
    currency: str | None


async def _tier_report(
    client: Any,
    d: Definition,
    tier: Any,
    cases: Sequence[EvalCase],
    repeat: int,
    unmet: list[str],
    cuts: dict[str, dict[str, float]],
) -> TierReport:
    single = dataclasses.replace(d, tiers=(tier,), failover_on=(), interpret=None)
    runs: list[list[_Row]] = []
    for _ in range(repeat):
        row = []
        for c in cases:
            res = await client.decide(single, c.input)
            attempts = res.envelope.attempts if res.ok else res.attempts
            latency = sum(a.latency_ms for a in attempts)
            cost = res.envelope.usage.cost if res.ok else None
            row.append(
                _Row(
                    res.envelope.answers if res.ok else None,
                    latency,
                    None if cost is None else cost.amount,
                    None if cost is None else cost.currency,
                )
            )
        runs.append(row)

    def value(x: _Row, q: str) -> str | None:
        a = None if x.answers is None else x.answers.get(q)
        return None if a is None else a.value

    def scored(q: str) -> list[Scored]:
        out = []
        for row in runs:
            for x, c in zip(row, cases, strict=True):
                a = None if x.answers is None else x.answers.get(q)
                out.append(Scored(None if a is None else a.confidence, a is not None and a.value == c.labels.get(q)))
        return out

    questions = {}
    for q in d.questions:
        xs = scored(q)
        questions[q] = QuestionReport(
            accuracy=accuracy(xs),
            brier=brier(xs),
            flip_rate=flip_rate([[_or_failed(value(x, q)) for x in row] for row in runs]),
        )
    cutoffs = {}
    for name, th in d.thresholds.items():
        fit = fit_cutoff(scored(th.on), th.objective)
        cutoffs[name] = fit
        if not fit.met:
            unmet.append(f"{name}@{tier.id}")
        if fit.cutoff is not None:
            cuts.setdefault(name, {})[tier.id] = fit.cutoff
    every = [x for row in runs for x in row]
    per_run_acc = [
        accuracy(
            [Scored(None, value(x, q) == c.labels.get(q)) for x, c in zip(row, cases, strict=True) for q in d.questions]
        )
        for row in runs
    ]
    latencies = [x.latency for x in every]
    priced = every and all(x.cost is not None for x in every) and every[0].currency is not None
    return TierReport(
        questions=MappingProxyType(questions),
        cutoffs=MappingProxyType(cutoffs),
        accuracy_stdev=_round(stdev(per_run_acc)),
        latency_ms=LatencyReport(percentile(latencies, 50), percentile(latencies, 95)),
        cost=FitCost(_round(sum(x.cost or 0 for x in every)), every[0].currency) if priced else None,  # type: ignore[arg-type]
        failures=sum(1 for x in every if x.answers is None),
    )


async def run_fit(
    d: Definition,
    cases: Sequence[EvalCase],
    *,
    adapters: Sequence[Adapter],
    prices: PriceTable | None = None,
    repeat: int = 1,
    yes: bool = False,
    now: Callable[[], float] | None = None,
) -> FitOutcome:
    """Without ``yes`` only the estimate is returned and nothing is called."""
    estimate = estimate_fit_cost(d, len(cases), repeat, prices)
    if not yes:
        return NeedsConfirmation(estimate)
    clock = now or _now_ms
    client = create_client(adapters=adapters, prices=prices, now=clock)
    tiers: dict[str, TierReport] = {}
    cuts: dict[str, dict[str, float]] = {}
    unmet: list[str] = []
    for tier in d.tiers:
        tiers[tier.id] = await _tier_report(client, d, tier, cases, repeat, unmet, cuts)
    report = FitReport(d.contract, len(cases), repeat, MappingProxyType(tiers))
    set_hash = sha256(canonicalize(to_json(list(cases))))
    if unmet:
        return ObjectivesUnmet(tuple(unmet), report, estimate, set_hash)
    lock = Lock(
        ContractRef(d.contract, emit(d).hash),
        MappingProxyType({k: MappingProxyType(v) for k, v in cuts.items()}),
        tiers=tuple(LockTier(t.id, None) for t in d.tiers),  # TODO(vendor-fact): provider descriptor hash
        eval=EvalProvenance(set_hash=set_hash, n=len(cases), repeat=repeat, at=_iso(clock()), objectives_met=True),
    )
    return FitOk(lock, report, estimate, set_hash)
