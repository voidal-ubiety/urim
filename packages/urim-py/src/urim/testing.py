"""A (test double): the adapter barrier and a scripted fake, mirroring urim-ts src/testing.ts.

Import from ``urim.testing``; nothing here makes a network call.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .errors import UrimError
from .types import WireReply, WireRequest


@dataclass(frozen=True)
class SendIO:
    """What the client hands an adapter for one attempt. ``credential`` is read from env at send time; never logged."""

    credential: str = field(repr=False)
    cancel: asyncio.Event
    http: Any = None  # an httpx.AsyncClient when the client was given one


class Adapter(Protocol):
    #: provider id this adapter serves (Tier.provider); "*" serves any tier (test doubles only)
    provider: str
    #: env var NAME holding the credential, or None
    credential_env: str | None

    async def send(self, req: WireRequest, io: SendIO) -> WireReply: ...


class FakeProvider:
    """Replays ``script[tier_id]`` steps: {"fail": type} | {"body": ..., "status"?: int} | {"hang": True}.

    ``cycle=True`` replays round-robin (eval sets, ``fit --repeat``). Keys starting with "_" are ignored.
    """

    provider = "*"
    credential_env: str | None = None

    def __init__(self, script: Mapping[str, Sequence[Mapping[str, Any]]], *, cycle: bool = False) -> None:
        self._script = script
        self._cycle = cycle
        self._cursor: dict[str, int] = {}
        self.calls: list[WireRequest] = []

    def _step(self, tier_id: str) -> Mapping[str, Any]:
        index = self._cursor.get(tier_id, 0)
        steps = self._script.get(tier_id)
        pos = index % len(steps) if self._cycle and steps else index
        if not steps or pos >= len(steps):
            raise RuntimeError(f"fake_provider: no scripted step {index} for {tier_id}")  # a test bug: fail fast
        self._cursor[tier_id] = index + 1
        return steps[pos]

    async def send(self, req: WireRequest, io: SendIO) -> WireReply:
        if io.cancel.is_set():
            raise UrimError("cancelled", "aborted before send", tier=req.tier_id)
        self.calls.append(req)
        step = self._step(req.tier_id)
        if "hang" in step:
            await asyncio.Event().wait()  # only cancellation or the deadline ends it
        if "fail" in step:
            raise UrimError(step["fail"], f"scripted {step['fail']}", tier=req.tier_id)
        return WireReply(step.get("status", 200), {}, step.get("body"), 0)


def fake_provider(script: Mapping[str, Sequence[Mapping[str, Any]]], *, cycle: bool = False) -> FakeProvider:
    return FakeProvider(script, cycle=cycle)
