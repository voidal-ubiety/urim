"""C: assemble the portable urim/1 envelope (typed, snake_case; ``boundary.to_json`` gives the urim-ts JSON)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from .camps.shared import TokenUsage
from .freeze import deep_freeze
from .types import (
    ABSENT,
    Answer,
    Attempt,
    ContractRef,
    Cost,
    Cut,
    Definition,
    Envelope,
    EnvelopeTier,
    Fallback,
    PriceEntry,
    PriceTable,
    PriceTableRef,
    Tier,
    Usage,
)


def _fallback(d: Definition, tier: Tier, attempts: Sequence[Attempt]) -> Fallback | None:
    primary = d.tiers[0] if d.tiers else None
    if primary is None or primary.id == tier.id:
        return None
    failed = [a for a in attempts if a.tier != tier.id]
    first = next((a for a in failed if a.tier == primary.id), failed[0] if failed else None)
    reason = (
        "provider_unavailable"
        if first is None or first.outcome == "ok"
        else "budget"
        if first.outcome == "skipped_budget"
        else first.outcome
    )
    return Fallback(primary.id, reason, len(failed))


def _estimate(e: PriceEntry, usage: TokenUsage | None) -> float | None:
    """Token price wins over flat per-call; output tokens priced only when the table says so."""
    if e.per_m_input_tokens is not ABSENT:
        tok = None if usage is None else usage.input_tokens
        if e.per_m_input_tokens is None or tok is None:
            return None
        out_tok = usage.output_tokens if usage is not None and usage.output_tokens is not None else 0
        per_out = 0 if e.per_m_output_tokens is ABSENT or e.per_m_output_tokens is None else e.per_m_output_tokens
        return (tok * e.per_m_input_tokens + out_tok * per_out) / 1_000_000
    return None if e.per_call is ABSENT else e.per_call


def _usage(tier: Tier, prices: PriceTable | None, usage: TokenUsage | None) -> Usage:
    entry = None if prices is None else prices.entries.get(tier.id)
    amount = None if entry is None else _estimate(entry, usage)
    cost = (
        None
        if entry is None or prices is None or amount is None
        else Cost(amount, entry.currency, "estimated", PriceTableRef(prices.id, prices.as_of, prices.url))
    )
    return Usage(None if usage is None else usage.input_tokens, None if usage is None else usage.output_tokens, cost)


def build_envelope(
    *,
    d: Definition,
    contract_hash: str,
    tier: Tier,
    answers: Mapping[str, Answer],
    cuts: Mapping[str, Cut],
    attempts: Sequence[Attempt],
    request_ids: Mapping[str, str],
    at: str,
    prices: PriceTable | None = None,
    usage: TokenUsage | None = None,
    raw: Any = ABSENT,
    interpret_failed: bool = False,
) -> Envelope:
    fb = _fallback(d, tier, attempts)
    return Envelope(
        envelope="urim/1",
        contract=ContractRef(d.contract, contract_hash),
        tier=EnvelopeTier(
            tier.id,
            tier.provider,
            tier.model,
            tier.version,
            tier.camp,
            tier.question_types,
            "primary" if fb is None else "fallback",
        ),
        answers=MappingProxyType(dict(answers)),
        thresholds=MappingProxyType(dict(cuts)),
        fallback=fb,
        attempts=tuple(attempts),
        usage=_usage(tier, prices, usage),
        request_ids=MappingProxyType(dict(request_ids)),
        at=at,
        raw=ABSENT if raw is ABSENT else deep_freeze(raw),
        interpret_failed=interpret_failed,
    )
