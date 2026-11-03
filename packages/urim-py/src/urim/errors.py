"""D: the one error class and its closed type list (design §5.3, D11). Mirrors urim-ts src/errors.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

ErrorType = Literal[
    "invalid_input",
    "invalid_definition",
    "lock_violation",
    "auth",
    "invalid_request",
    "refused",
    "limit_exceeded",
    "timeout",
    "provider_unavailable",
    "rate_limited",
    "quota_exceeded",
    "nonconformant_response",
    "budget",
    "cancelled",
    "all_tiers_failed",
    "internal",
]
ERROR_TYPES: frozenset[str] = frozenset(get_args(ErrorType))

#: Types that ``failover.on`` may list. Everything else always abstains.
FAILOVER_TYPES: frozenset[str] = frozenset(
    {"timeout", "provider_unavailable", "rate_limited", "quota_exceeded", "nonconformant_response", "budget"}
)


@dataclass(frozen=True)
class Issue:
    path: str
    message: str


class UrimError(Exception):
    """Immutable after construction. ``retry_after_ms`` is information only; Urim never sleeps on it."""

    __slots__ = ("_frozen", "issues", "request_id", "retry_after_ms", "retryable", "status", "tier", "type")
    type: ErrorType
    retryable: bool
    tier: str | None
    status: int | None
    request_id: str | None
    retry_after_ms: int | None
    issues: tuple[Issue, ...] | None

    def __init__(
        self,
        type: ErrorType,
        message: str,
        *,
        tier: str | None = None,
        status: int | None = None,
        request_id: str | None = None,
        retry_after_ms: int | None = None,
        issues: tuple[Issue, ...] | list[Issue] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if type not in ERROR_TYPES:
            raise ValueError(f"unknown ErrorType {type!r}")
        super().__init__(message)
        for k, v in (
            ("type", type),
            ("retryable", type in FAILOVER_TYPES),
            ("tier", tier),
            ("status", status),
            ("request_id", request_id),
            ("retry_after_ms", retry_after_ms),
            ("issues", None if issues is None else tuple(issues)),
        ):
            object.__setattr__(self, k, v)
        self.__cause__ = cause
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_frozen", False) and name != "__cause__" and name != "__traceback__":
            raise AttributeError("UrimError is immutable")
        object.__setattr__(self, name, value)

    @property
    def message(self) -> str:
        return str(self.args[0]) if self.args else ""


def invalid_definition(issues: list[Issue]) -> UrimError:
    return UrimError("invalid_definition", "; ".join(f"{i.path}: {i.message}" for i in issues), issues=issues)
