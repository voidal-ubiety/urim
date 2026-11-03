"""D: plain data shapes (mirrors urim-ts src/types.ts). Frozen dataclasses; mappings are read-only views.

Casing rule (accepted 2026-10-29): every attribute here is snake_case. JSON (contract, lockfile, envelope,
settled record) is camelCase exactly as urim-ts writes it; the ONE mapping between the two is ``urim.boundary``.
Optional JSON members that may be absent (as opposed to null) default to ``ABSENT``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import KW_ONLY, dataclass, field
from types import MappingProxyType
from typing import Any, Final, Literal, Protocol

from .errors import Issue

Camp = Literal["systemone", "decisions"]
QuestionType = Literal["noul", "choice", "score"]
ConfidenceSource = Literal["native", "urim_derived"]
# systemone_normalized: |2p - 1| from a yes/no probability, the systemone request format's normalized formula.
# vendor_unspecified: the vendor's own number; Urim does not know or assert its formula.
ConfidenceFormula = Literal["systemone_normalized", "vendor_unspecified"]
#: The formula behind `confidence`, per question type (hashed into the contract). Mirrors urim-ts CONFIDENCE_RULE.
CONFIDENCE_RULE: Final[Mapping[str, ConfidenceFormula]] = MappingProxyType(
    {"noul": "systemone_normalized", "choice": "vendor_unspecified", "score": "vendor_unspecified"}
)
CostSource = Literal["per_call", "estimated_pre_call"]


class _Absent(enum.Enum):
    """An optional JSON member that is not present (distinct from JSON null). Singleton, falsy.

    An enum member so type checkers narrow ``x is ABSENT`` / ``x is not ABSENT``.
    """

    ABSENT = "ABSENT"

    def __repr__(self) -> str:
        return "ABSENT"

    def __bool__(self) -> bool:
        return False


ABSENT: Final = _Absent.ABSENT


@dataclass(frozen=True)
class Tier:
    id: str
    provider: str
    model: str
    version: str
    camp: Camp
    question_types: tuple[QuestionType, ...]


@dataclass(frozen=True)
class Question:
    type: QuestionType
    prompt: str
    options: Mapping[str, str]  # ordered; for score, order = ascending level


@dataclass(frozen=True)
class Objective:
    """What `urim fit` tunes a threshold for; either target may be absent."""

    min_precision: float | _Absent = ABSENT
    escalation_rate: float | _Absent = ABSENT


@dataclass(frozen=True)
class Threshold:
    on: str
    default: float | None
    objective: Objective


@dataclass(frozen=True)
class ParseOk:
    value: Any
    ok: Literal[True] = True


@dataclass(frozen=True)
class ParseFail:
    issues: tuple[Issue, ...]
    ok: Literal[False] = False


class SchemaAdapter(Protocol):
    """Internal schema barrier (D9). Pydantic is adapted to this; nothing else in the core sees Pydantic."""

    def parse(self, value: Any) -> ParseOk | ParseFail: ...
    def to_json_schema(self) -> Any: ...


@dataclass(frozen=True, eq=False)  # identity, like the TS object a client registers
class Definition:
    contract: str
    tiers: tuple[Tier, ...]
    input: SchemaAdapter
    questions: Mapping[str, Question]
    failover_on: tuple[str, ...]
    thresholds: Mapping[str, Threshold]
    confidence: Mapping[str, ConfidenceFormula] = field(default_factory=lambda: CONFIDENCE_RULE)
    prepare: Callable[[Any], Any] | None = None
    interpret: Callable[..., Any] | None = None


@dataclass(frozen=True)
class Answer:
    value: str
    confidence: float | None
    confidence_source: ConfidenceSource | None
    _: KW_ONLY
    #: urim/1 minor addition (0.0.1); None when confidence is None; ABSENT (omitted) when built by hand or read
    #: from an older envelope. Keyword-only so positional callers keep working.
    confidence_formula: ConfidenceFormula | _Absent | None = ABSENT
    native: Mapping[str, Any] = field(kw_only=False)  # {name, value, confidence}: vendor data, never re-cased


@dataclass(frozen=True)
class Cut:
    value: float | None
    source: Literal["lock", "default", "none"]
    passes: bool
    confidence: float | None


@dataclass(frozen=True)
class WireRequest:
    tier_id: str
    camp: Camp
    path: str
    url: str
    body: Any  # vendor-native body


@dataclass(frozen=True)
class WireReply:
    status: int
    headers: Mapping[str, str]
    body: Any
    latency_ms: float = 0


@dataclass(frozen=True)
class Attempt:
    tier: str
    outcome: str  # "ok" | "skipped_budget" | ErrorType
    latency_ms: float


@dataclass(frozen=True)
class PlanStep:
    tier: Tier
    action: Literal["call", "skip"]
    estimated_cost: float | None
    cost_source: CostSource | None
    estimated_input_tokens: int | None = None
    reason: Literal["budget"] | None = None


@dataclass(frozen=True)
class Plan:
    contract: str
    steps: tuple[PlanStep, ...]
    #: effective total deadline (explain only); ABSENT when there is none
    deadline_ms: float | _Absent = ABSENT


@dataclass(frozen=True)
class Budget:
    max_cost: float
    currency: str


@dataclass(frozen=True)
class ContractRef:
    id: str
    hash: str


@dataclass(frozen=True)
class LockTier:
    id: str
    descriptor_hash: str | None


@dataclass(frozen=True)
class EvalProvenance:
    set_hash: str
    n: int
    repeat: int
    at: str
    objectives_met: bool


@dataclass(frozen=True)
class Lock:
    contract: ContractRef
    cuts: Mapping[str, Mapping[str, float]]
    lock: Literal[1] = 1
    tiers: tuple[LockTier, ...] | _Absent = ABSENT
    eval: EvalProvenance | _Absent = ABSENT


@dataclass(frozen=True)
class PriceEntry:
    currency: str
    per_call: float | _Absent = ABSENT
    per_m_input_tokens: float | _Absent | None = ABSENT
    per_m_output_tokens: float | _Absent | None = ABSENT


@dataclass(frozen=True)
class PriceTable:
    id: str
    as_of: str
    url: str
    entries: Mapping[str, PriceEntry]


@dataclass(frozen=True)
class PriceTableRef:
    id: str
    as_of: str
    url: str


@dataclass(frozen=True)
class Cost:
    amount: float
    currency: str
    source: Literal["estimated", "reported"]
    price_table: PriceTableRef | _Absent = ABSENT


@dataclass(frozen=True)
class Usage:
    input_tokens: float | None
    output_tokens: float | None
    cost: Cost | None


@dataclass(frozen=True)
class EnvelopeTier:
    id: str
    provider: str
    model: str
    version: str
    camp: Camp
    question_types: tuple[QuestionType, ...]
    role: Literal["primary", "fallback"]


@dataclass(frozen=True)
class Fallback:
    from_: str
    reason: str
    attempts: int


@dataclass(frozen=True)
class Envelope:
    envelope: Literal["urim/1"]
    contract: ContractRef
    tier: EnvelopeTier
    answers: Mapping[str, Answer]
    thresholds: Mapping[str, Cut]
    fallback: Fallback | None
    attempts: tuple[Attempt, ...]
    usage: Usage
    request_ids: Mapping[str, str]
    at: str
    raw: Any = ABSENT
    interpret_failed: bool = False  # written only when true


@dataclass(frozen=True)
class SettledContract:
    id: str
    hash: str | None


@dataclass(frozen=True)
class SettledError:
    type: str
    message: str
    tier: str | None


@dataclass(frozen=True)
class Settled:
    """D3: the one record on_settled receives for every settled decide call. Uniform members; frozen."""

    settled: Literal["urim/1"]
    outcome: Literal["ok", "interpret_failed", "abstain"]
    contract: SettledContract
    envelope: Envelope | None
    attempts: tuple[Attempt, ...]
    at: str
    error: SettledError | None


@dataclass(frozen=True)
class Success:
    value: Any
    envelope: Envelope
    fallback: Fallback | None
    thresholds: Mapping[str, Cut]
    ok: Literal[True] = True


@dataclass(frozen=True)
class Failure:
    error: Any  # UrimError
    attempts: tuple[Attempt, ...]
    ok: Literal[False] = False
