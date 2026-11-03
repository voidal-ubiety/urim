"""urim.testing.fake_provider: same script semantics as urim-ts src/testing.ts."""

import asyncio

import pytest

from urim import UrimError
from urim.testing import SendIO, fake_provider
from urim.types import WireRequest


def req(tier="t@1"):
    return WireRequest(tier, "systemone", "/v1/systemone", "https://example.invalid", {})


def send(fake, r, cancel=None):
    return asyncio.run(fake.send(r, SendIO(credential="", cancel=cancel or asyncio.Event())))


def test_steps_in_order_then_missing_step_is_a_plain_error():
    fake = fake_provider({"t@1": [{"body": {"a": 1}}, {"body": "x", "status": 529}], "_notice": []})
    first = send(fake, req())
    assert (first.status, first.body, first.latency_ms) == (200, {"a": 1}, 0)
    assert send(fake, req()).status == 529
    with pytest.raises(RuntimeError) as e:
        send(fake, req())
    assert not isinstance(e.value, UrimError)
    assert [c.tier_id for c in fake.calls] == ["t@1"] * 3
    assert fake.provider == "*"


def test_fail_step_raises_typed_error_with_tier():
    with pytest.raises(UrimError) as e:
        send(fake_provider({"t@1": [{"fail": "rate_limited"}]}), req())
    assert (e.value.type, e.value.tier) == ("rate_limited", "t@1")


def test_cycle_replays_round_robin():
    fake = fake_provider({"t@1": [{"body": 1}, {"body": 2}]}, cycle=True)
    assert [send(fake, req()).body for _ in range(5)] == [1, 2, 1, 2, 1]


def test_cancelled_before_send_records_no_call():
    ev = asyncio.Event()
    ev.set()
    fake = fake_provider({"t@1": [{"body": 1}]})
    with pytest.raises(UrimError) as e:
        send(fake, req(), ev)
    assert e.value.type == "cancelled" and fake.calls == []


def test_hang_only_ends_by_cancellation():
    async def go():
        fake = fake_provider({"t@1": [{"hang": True}]})
        task = asyncio.ensure_future(fake.send(req(), SendIO(credential="", cancel=asyncio.Event())))
        done, _ = await asyncio.wait({task}, timeout=0.05)
        assert not done
        task.cancel()

    asyncio.run(go())
