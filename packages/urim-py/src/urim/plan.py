"""C: plan-then-execute. The plan is data. Mirrors urim-ts src/plan.ts incl. the slice 4b pre-call estimate.

Prices are a ``PriceTable`` (parse the shared JSON with ``boundary.parse_price_table``).
"""

from __future__ import annotations

from typing import Any

from .camps import encode_request
from .errors import FAILOVER_TYPES
from .jsonfmt import stringify
from .types import ABSENT, Budget, Definition, Plan, PlanStep, PriceTable, Tier, WireRequest

_UNSET: Any = object()


def estimate_input_tokens(req: WireRequest) -> int:
    """UTF-8 byte length of JSON.stringify(body). Same number as urim-ts. Unverified, conservative heuristic:
    byte-level BPE tokens cover >= 1 byte each; vendor tokenizers and prompt overhead are undocumented."""
    return len(stringify(req.body).encode("utf-8", "surrogatepass"))


def _estimate(
    d: Definition, tier: Tier, prices: PriceTable | None, budget: Budget | None, input: Any
) -> tuple[float | None, str | None, int | None]:
    entry = None if prices is None else prices.entries.get(tier.id)
    if entry is None or (budget is not None and entry.currency != budget.currency):
        return None, None, None
    if entry.per_call is not ABSENT:
        return entry.per_call, "per_call", None
    per_m = None if entry.per_m_input_tokens is ABSENT else entry.per_m_input_tokens
    if per_m is None or input is _UNSET:
        return None, None, None  # unknown: never skipped (D5)
    tokens = estimate_input_tokens(encode_request(d, tier, input))
    return tokens * per_m / 1_000_000, "estimated_pre_call", tokens


def plan_attempts(
    d: Definition, *, budget: Budget | None = None, prices: PriceTable | None = None, input: Any = _UNSET
) -> Plan:
    applies = budget is not None and "budget" in d.failover_on
    steps = []
    for t in d.tiers:
        cost, source, tokens = _estimate(d, t, prices, budget, input)
        over = applies and cost is not None and budget is not None and cost > budget.max_cost
        steps.append(PlanStep(t, "skip" if over else "call", cost, source, tokens, "budget" if over else None))  # type: ignore[arg-type]
    return Plan(d.contract, tuple(steps))


explain = plan_attempts


def next_step(d: Definition, failure: str) -> str:
    return "next" if failure in FAILOVER_TYPES and failure in d.failover_on else "abstain"
