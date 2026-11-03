"""A: the edge. ``create_client`` binds adapters, env, clock and hooks; ``decide`` is the one thin async I/O loop
over the pure plan. Mirrors urim-ts src/client.ts (D3 hooks, D4/D6 startup checks, D10 raw, D11 interpret)."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import inspect
import logging
import math
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any, Literal, cast

from .camps import decode_reply, encode_request, request_id_of
from .cuts import resolve_cuts
from .emit import emit
from .envelope import build_envelope
from .errors import UrimError
from .plan import _UNSET, next_step, plan_attempts
from .testing import Adapter, SendIO
from .types import (
    ABSENT,
    Attempt,
    Budget,
    Definition,
    Envelope,
    Failure,
    Lock,
    Plan,
    PriceTable,
    Settled,
    SettledContract,
    SettledError,
    Success,
    Tier,
    WireReply,
    WireRequest,
)

_log = logging.getLogger("urim")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

OnSettled = Callable[[Settled], "Awaitable[None] | None"]
OnHookError = Callable[[BaseException, Settled], None]


def _now_ms() -> int:
    return time.time_ns() // 1_000_000  # integer ms, like Date.now()


def _iso(ms: float) -> str:
    """new Date(ms).toISOString()."""
    return (_EPOCH + timedelta(milliseconds=int(ms))).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ---- startup checks (C) ----


def _missing_cuts(d: Definition, lock: Lock) -> list[str]:
    return [
        f"{name}@{tier.id}"
        for name, t in d.thresholds.items()
        for tier in d.tiers
        if tier.id not in lock.cuts.get(name, {}) and t.default is None
    ]


def _prod_problems(d: Definition, lock: Lock | None) -> list[str]:
    if lock is None:
        return [f"{d.contract}: no lock"]
    h = emit(d).hash
    if lock.contract.hash != h:
        return [f"{d.contract}: lock hash {lock.contract.hash} != emitted {h}"]
    return [f"{d.contract}: no cutoff for {m}" for m in _missing_cuts(d, lock)]


def missing_adapters(d: Definition, adapters: Sequence[Adapter]) -> list[str]:
    """Every tier of a registered decision needs an adapter (exact provider or the "*" test double)."""
    if any(a.provider == "*" for a in adapters):
        return []
    return [
        f"{d.contract}: no adapter for provider {t.provider} (tier {t.id})"
        for t in d.tiers
        if not any(a.provider == t.provider for a in adapters)
    ]


def _contract_hash(d: Definition) -> str | None:
    try:
        return emit(d).hash
    except Exception:
        return None


def settled_record(
    d: Definition,
    outcome: Literal["ok", "interpret_failed", "abstain"],
    envelope: Envelope | None,
    error: UrimError | None,
    attempts: Sequence[Attempt],
    at: str,
) -> Settled:
    return Settled(
        "urim/1",
        outcome,
        SettledContract(d.contract, envelope.contract.hash if envelope else _contract_hash(d)),
        envelope,
        tuple(attempts),
        at,
        None if error is None else SettledError(error.type, error.message, error.tier),
    )


# ---- one attempt (A): send with cancel + deadline; every outcome becomes data ----


def _swallow(task: asyncio.Future[Any]) -> None:
    if not task.cancelled():
        task.exception()  # retrieved: an abandoned send must not warn "exception was never retrieved"


async def _send_once(
    adapter: Adapter,
    tier: Tier,
    req: WireRequest,
    credential: str,
    http: Any,
    cancel: asyncio.Event | None,
    remaining_ms: float | None,
) -> tuple[WireReply | UrimError, bool]:
    """Returns (outcome, deadline_spent). deadline_spent: the deadline timeout fired (not an adapter timeout error)."""
    if remaining_ms is not None and remaining_ms <= 0:
        return UrimError("timeout", f"deadline exhausted before {tier.id}", tier=tier.id), True
    io_cancel = asyncio.Event()
    send = asyncio.ensure_future(adapter.send(req, SendIO(credential, io_cancel, http)))
    send.add_done_callback(_swallow)
    caller = None if cancel is None else asyncio.ensure_future(cancel.wait())
    try:
        done, _ = await asyncio.wait(
            {send} if caller is None else {send, caller},
            timeout=None if remaining_ms is None else remaining_ms / 1000,
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        if caller is not None:
            caller.cancel()
        if not send.done():
            io_cancel.set()
            send.cancel()
    if send not in done:
        reason: Literal["cancelled", "timeout"] = "cancelled" if caller is not None and caller in done else "timeout"
        return UrimError(reason, f"{reason} during {tier.id}", tier=tier.id), reason == "timeout"
    if send.cancelled():
        raise asyncio.CancelledError
    cause = send.exception()
    if cause is None:
        return send.result(), False
    if isinstance(cause, UrimError):
        return cause, False
    return UrimError("internal", f"adapter threw for {tier.id}", tier=tier.id, cause=cause), False


class Client:
    """Built by ``create_client``. ``decide`` never raises for a vendor or input problem: it returns a Failure."""

    def __init__(
        self,
        *,
        adapters: Sequence[Adapter],
        env: Mapping[str, str] | None,
        mode: Literal["dev", "prod"],
        decisions: Sequence[Definition],
        locks: Sequence[Lock],
        prices: PriceTable | None,
        budget: Budget | None,
        deadline_ms: float | None,
        raw: bool,
        now: Callable[[], float] | None,
        http: Any,
        on_settled: OnSettled | None,
        on_hook_error: OnHookError | None,
    ) -> None:
        self._adapters = tuple(adapters)
        self._env = env
        self._mode = mode
        self._registered = set(decisions)
        self._locks = tuple(locks)
        self._prices = prices
        if deadline_ms is not None and not (
            isinstance(deadline_ms, (int, float))
            and not isinstance(deadline_ms, bool)
            and math.isfinite(deadline_ms)
            and deadline_ms > 0
        ):
            raise UrimError("invalid_definition", f"deadline_ms must be a finite number > 0, got {deadline_ms!r}")
        self._budget = budget
        self._deadline_ms = deadline_ms
        self._raw = raw
        self._now = now or _now_ms
        self._http = http
        self._on_settled = on_settled
        self._on_hook_error = on_hook_error or self._warn_once
        self._warned = False
        self._pending: set[asyncio.Task[None]] = set()
        if mode == "prod":
            problems = [p for d in decisions for p in _prod_problems(d, self._lock_for(d))]
            if problems:
                raise UrimError("lock_violation", "; ".join(problems))
            unrouted = [p for d in decisions for p in missing_adapters(d, self._adapters)]
            if unrouted:
                raise UrimError("invalid_definition", "; ".join(unrouted))

    # ---- hooks (D3): fire-and-forget on a frozen record; errors isolated; flush() is the join point ----

    def _warn_once(self, err: BaseException, record: Settled) -> None:
        if not self._warned:
            self._warned = True
            _log.warning("urim: on_settled failed: %s", err)

    async def _run_hook(self, record: Settled) -> None:
        await asyncio.sleep(0)  # never inside the caller's await, like Promise.resolve().then
        try:
            r = self._on_settled(record)  # type: ignore[misc]
            if inspect.isawaitable(r):
                await r
        except Exception as err:
            with contextlib.suppress(Exception):
                self._on_hook_error(err, record)

    def _settle(self, record: Settled) -> None:
        if self._on_settled is None:
            return
        task = asyncio.ensure_future(self._run_hook(record))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def flush(self) -> None:
        while self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)

    # ---- decide ----

    def _lock_for(self, d: Definition) -> Lock | None:
        return next((lk for lk in self._locks if lk.contract.id == d.contract), None)

    def _adapter_for(self, tier: Tier) -> Adapter | None:
        return next((a for a in self._adapters if a.provider == tier.provider), None) or next(
            (a for a in self._adapters if a.provider == "*"), None
        )

    def _credential(self, adapter: Adapter) -> str:
        name = getattr(adapter, "credential_env", None)
        return "" if name is None or self._env is None else self._env.get(name, "")

    async def decide(
        self,
        d: Definition,
        input: Any,
        *,
        cancel: asyncio.Event | None = None,
        deadline_ms: Any = _UNSET,
        raw: bool | None = None,
        budget: Budget | None = None,
    ) -> Success | Failure:
        """``deadline_ms``: not passed uses the client default; ``None`` means no deadline for this call."""
        deadline_ms = self._deadline_for(deadline_ms)
        started = self._now()
        at = _iso(started)

        def fail(error: UrimError, attempts: Sequence[Attempt]) -> Failure:
            self._settle(settled_record(d, "abstain", None, error, attempts, at))
            return Failure(error, tuple(attempts))

        if self._mode == "prod" and d not in self._registered:
            return fail(
                UrimError("lock_violation", f"{d.contract} was not checked at startup (pass it in decisions)"), []
            )
        parsed = d.input.parse(input)
        if not parsed.ok:
            return fail(UrimError("invalid_input", "input does not match the schema", issues=parsed.issues), [])
        prepared = parsed.value if d.prepare is None else d.prepare(parsed.value)
        plan = plan_attempts(d, budget=self._budget if budget is None else budget, prices=self._prices, input=prepared)

        attempts: list[Attempt] = []
        request_ids: dict[str, str] = {}
        last_error: UrimError | None = None
        answered = None
        # Once the deadline timeout fires the deadline is spent, whatever now() reads (asyncio may fire a timer
        # up to clock_resolution early). Later tiers then fail as timeout without a call, as when remaining <= 0.
        deadline_spent = False
        for step in plan.steps:
            if cancel is not None and cancel.is_set():
                return fail(UrimError("cancelled", "aborted"), attempts)
            if step.action == "skip":
                attempts.append(Attempt(step.tier.id, "skipped_budget", 0))
                continue
            adapter = self._adapter_for(step.tier)
            if adapter is None:
                return fail(
                    UrimError("invalid_definition", f"no adapter for provider {step.tier.provider}", tier=step.tier.id),
                    attempts,
                )
            t0 = self._now()
            remaining = None if deadline_ms is None else 0 if deadline_spent else deadline_ms - (t0 - started)
            sent, spent = await _send_once(
                adapter,
                step.tier,
                encode_request(d, step.tier, prepared),
                self._credential(adapter),
                self._http,
                cancel,
                remaining,
            )
            deadline_spent = deadline_spent or spent
            decoded = decode_reply(d, step.tier, sent) if isinstance(sent, WireReply) else None
            latency = self._now() - t0
            if isinstance(sent, WireReply) and (rid := request_id_of(step.tier, sent)) is not None:
                request_ids[step.tier.id] = rid
            if decoded is not None and decoded.ok:
                attempts.append(Attempt(step.tier.id, "ok", latency))
                assert isinstance(sent, WireReply)
                answered = (step.tier, decoded, sent)
                break
            error = decoded.error if decoded is not None else sent
            assert isinstance(error, UrimError)  # sent is a UrimError exactly when there was no reply to decode
            attempts.append(Attempt(step.tier.id, error.type, latency))
            if next_step(d, error.type) == "abstain":
                return fail(error, attempts)
            last_error = error
        if answered is None:
            return fail(
                UrimError("all_tiers_failed", f"every tier failed or was skipped for {d.contract}", cause=last_error),
                attempts,
            )

        tier, decoded, reply = answered
        cuts = MappingProxyType(resolve_cuts(d, tier, decoded.answers, mode=self._mode, lock=self._lock_for(d)))
        want_raw = self._raw if raw is None else raw

        def envelope_for(interpret_failed: bool) -> Envelope:
            return build_envelope(
                d=d,
                contract_hash=emit(d).hash,
                tier=tier,
                answers=decoded.answers,
                cuts=cuts,
                attempts=attempts,
                request_ids=request_ids,
                at=at,
                prices=self._prices,
                usage=decoded.usage,
                raw=reply.body if want_raw else ABSENT,
                interpret_failed=interpret_failed,
            )

        answers = MappingProxyType(dict(decoded.answers))
        try:
            value = answers if d.interpret is None else d.interpret(answers=answers, cut=cuts)
        except Exception:
            # D11: telemetry still sees it; the caller gets the original error, no fallback
            self._settle(settled_record(d, "interpret_failed", envelope_for(True), None, attempts, at))
            raise
        envelope = envelope_for(False)
        self._settle(settled_record(d, "ok", envelope, None, attempts, at))
        return Success(value, envelope, envelope.fallback, cuts)

    async def decide_or_throw(self, d: Definition, input: Any, **opts: Any) -> Success:
        r = await self.decide(d, input, **opts)
        if not r.ok:
            raise r.error
        assert isinstance(r, Success)
        return r

    def _deadline_for(self, per_call: Any) -> float | None:
        return self._deadline_ms if per_call is _UNSET else cast("float | None", per_call)

    def explain(
        self, d: Definition, *, budget: Budget | None = None, input: Any = _UNSET, deadline_ms: Any = _UNSET
    ) -> Plan:
        """The plan decide would follow. Without input, token-priced tiers show unknown cost and are never skipped."""
        parsed = None if input is _UNSET else d.input.parse(input)
        prepared = (
            _UNSET
            if parsed is None or not parsed.ok
            else (parsed.value if d.prepare is None else d.prepare(parsed.value))
        )
        plan = plan_attempts(d, budget=self._budget if budget is None else budget, prices=self._prices, input=prepared)
        effective = self._deadline_for(deadline_ms)
        return plan if effective is None else dataclasses.replace(plan, deadline_ms=effective)


def create_client(
    *,
    adapters: Sequence[Adapter],
    env: Mapping[str, str] | None = None,
    mode: Literal["dev", "prod"] = "dev",
    decisions: Sequence[Definition] = (),
    locks: Sequence[Lock] = (),
    prices: PriceTable | None = None,
    budget: Budget | None = None,
    deadline_ms: float | None = None,
    raw: bool = False,
    now: Callable[[], float] | None = None,
    http: Any = None,
    on_settled: OnSettled | None = None,
    on_hook_error: OnHookError | None = None,
) -> Client:
    """``env`` is where credentials are read at send time (pass ``os.environ`` explicitly; default: none).
    ``deadline_ms`` is the default total deadline across tiers (finite, > 0; default: none); a call's
    ``deadline_ms`` overrides it and ``deadline_ms=None`` on a call opts out.
    ``now`` returns epoch milliseconds. ``http`` is an optional ``httpx.AsyncClient`` handed to adapters."""
    return Client(
        adapters=adapters,
        env=env,
        mode=mode,
        decisions=decisions,
        locks=locks,
        prices=prices,
        budget=budget,
        deadline_ms=deadline_ms,
        raw=raw,
        now=now,
        http=http,
        on_settled=on_settled,
        on_hook_error=on_hook_error,
    )
