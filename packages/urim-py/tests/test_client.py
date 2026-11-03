"""Client semantics mirrored from urim-ts test/client.test.ts.

The shared-vector scenarios are in test_client_vectors.
"""

import asyncio
import dataclasses
import logging

import pytest
from conftest import CLEF, JEV, PRICES, SHARED, TRIAGE, load

from urim import UrimError, emit
from urim.client import create_client
from urim.testing import SendIO, fake_provider
from urim.types import ABSENT, Budget, ContractRef, Lock, Settled

OK = next(v for v in load(SHARED / "client.vectors.json") if v["name"] == "primary ok")["script"][JEV.id][0]
INPUT = {"report": "db down"}


def good_lock(cuts=None):
    return Lock(ContractRef(TRIAGE.contract, emit(TRIAGE).hash), cuts or {"auto_route": {JEV.id: 0.5, CLEF.id: 0.5}})


def run(coro):
    return asyncio.run(coro)


def decide(client, d=TRIAGE, inp=INPUT, **kw):
    async def go():
        try:
            return await client.decide(d, inp, **kw)
        finally:
            await client.flush()

    return run(go())


# --- startup checks (D4/D6) ---
@pytest.mark.parametrize(
    "locks,pattern",
    [
        ((), "no lock"),
        ((dataclasses.replace(good_lock(), contract=ContractRef(TRIAGE.contract, "sha256:stale")),), "!= emitted"),
        ((good_lock({"auto_route": {JEV.id: 0.5}}),), "auto_route"),
    ],
)
def test_prod_startup_lock_problems(locks, pattern):
    with pytest.raises(UrimError, match=pattern) as e:
        create_client(adapters=[fake_provider({})], mode="prod", decisions=[TRIAGE], locks=locks)
    assert e.value.type == "lock_violation"


def test_prod_good_lock_starts_and_dev_needs_none():
    create_client(adapters=[fake_provider({})], mode="prod", decisions=[TRIAGE], locks=[good_lock()])
    create_client(adapters=[], decisions=[TRIAGE])


def test_prod_missing_adapter_is_startup_invalid_definition_naming_providers():
    with pytest.raises(UrimError) as e:
        create_client(adapters=[], mode="prod", decisions=[TRIAGE], locks=[good_lock()])
    assert e.value.type == "invalid_definition"
    assert "cloudflare" in e.value.message and "fake-systemone" in e.value.message


def test_prod_unregistered_decision_abstains_with_lock_violation():
    r = decide(create_client(adapters=[fake_provider({})], mode="prod", decisions=[], locks=[]))
    assert not r.ok and r.error.type == "lock_violation"


def test_dev_missing_adapter_is_decide_time_invalid_definition():
    r = decide(create_client(adapters=[], decisions=[TRIAGE]))
    assert not r.ok and r.error.type == "invalid_definition"


# --- loop ---
def test_prepare_runs_before_encode():
    fake = fake_provider({JEV.id: [OK]})
    d = dataclasses.replace(TRIAGE, prepare=lambda i: {"report": i["report"].upper()})
    decide(create_client(adapters=[fake]), d)
    assert fake.calls[0].body["state"] == {"report": "DB DOWN"}


def test_unexpected_adapter_exception_becomes_internal_with_cause():
    r = decide(create_client(adapters=[fake_provider({})]))
    assert not r.ok and r.error.type == "internal" and isinstance(r.error.__cause__, RuntimeError)


def test_deadline_is_timeout_and_exhausted_deadline_skips_the_call():
    fake = fake_provider({JEV.id: [{"hang": True}], CLEF.id: [OK]})
    r = decide(create_client(adapters=[fake]), deadline_ms=30)
    assert not r.ok and r.error.type == "all_tiers_failed"
    assert [a.outcome for a in r.attempts] == ["timeout", "timeout"]
    assert len(fake.calls) == 1


def test_deadline_firing_under_a_frozen_clock_ends_the_chain():
    # early-fire race: measured elapsed time stays 0, so only the fired timeout says the deadline is spent
    fake = fake_provider({JEV.id: [{"hang": True}], CLEF.id: [OK]})
    r = decide(create_client(adapters=[fake], now=lambda: 0), deadline_ms=5)
    assert not r.ok and r.error.type == "all_tiers_failed"
    assert [a.outcome for a in r.attempts] == ["timeout", "timeout"]
    assert [c.tier_id for c in fake.calls] == [JEV.id]


def test_adapter_timeout_error_does_not_spend_the_deadline():
    fake = fake_provider({JEV.id: [{"fail": "timeout"}], CLEF.id: [OK]})
    r = decide(create_client(adapters=[fake], now=lambda: 0), deadline_ms=1000)
    assert r.ok
    assert [c.tier_id for c in fake.calls] == [JEV.id, CLEF.id]


# --- client-wide default deadline ---
@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), "5", True])
def test_create_client_rejects_a_deadline_that_is_not_a_finite_number_above_0(bad):
    with pytest.raises(UrimError) as e:
        create_client(adapters=[], deadline_ms=bad)
    assert e.value.type == "invalid_definition"


def test_client_deadline_applies_when_the_call_sets_none():
    fake = fake_provider({JEV.id: [{"hang": True}], CLEF.id: [OK]})
    r = decide(create_client(adapters=[fake], now=lambda: 0, deadline_ms=5))
    assert not r.ok and r.error.type == "all_tiers_failed"
    assert [a.outcome for a in r.attempts] == ["timeout", "timeout"]
    assert [c.tier_id for c in fake.calls] == [JEV.id]


def test_per_call_deadline_overrides_the_client_default():
    fake = fake_provider({JEV.id: [OK]})
    r = decide(create_client(adapters=[fake], now=lambda: 0, deadline_ms=1000), deadline_ms=0)
    assert not r.ok
    assert [a.outcome for a in r.attempts] == ["timeout", "timeout"]
    assert fake.calls == []


def test_per_call_deadline_none_opts_out_of_the_client_default():
    fake = fake_provider({JEV.id: [OK, OK]})

    class Slow:
        provider = fake.provider

        async def send(self, req, io):
            await asyncio.sleep(0.03)
            return await fake.send(req, io)

    c = create_client(adapters=[Slow()], deadline_ms=5)
    assert not decide(c).ok
    assert decide(c, deadline_ms=None).ok


def test_explain_shows_the_effective_deadline():
    assert create_client(adapters=[]).explain(TRIAGE).deadline_ms is ABSENT
    c = create_client(adapters=[], deadline_ms=5)
    assert c.explain(TRIAGE).deadline_ms == 5
    assert c.explain(TRIAGE, deadline_ms=50).deadline_ms == 50
    assert c.explain(TRIAGE, deadline_ms=None).deadline_ms is ABSENT


def test_cancel_event_set_before_decide():
    ev = asyncio.Event()
    ev.set()
    fake = fake_provider({JEV.id: [OK]})
    r = decide(create_client(adapters=[fake]), cancel=ev)
    assert not r.ok and r.error.type == "cancelled" and fake.calls == []


def test_cancel_event_set_while_waiting():
    async def go():
        ev = asyncio.Event()
        client = create_client(adapters=[fake_provider({JEV.id: [{"hang": True}]})])
        asyncio.get_running_loop().call_later(0.02, ev.set)
        return await client.decide(TRIAGE, INPUT, cancel=ev)

    r = run(go())
    assert not r.ok and r.error.type == "cancelled" and [a.outcome for a in r.attempts] == ["cancelled"]


def test_task_cancellation_propagates():
    async def go():
        client = create_client(adapters=[fake_provider({JEV.id: [{"hang": True}]})])
        task = asyncio.ensure_future(client.decide(TRIAGE, INPUT))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(go())


def test_credential_is_read_from_env_at_send_time():
    seen = []

    class Spy:
        provider = "*"
        credential_env = "SPY_KEY"

        async def send(self, req, io: SendIO):
            seen.append(io.credential)
            raise UrimError("auth", "no")

    env = {}
    client = create_client(adapters=[Spy()], env=env)
    decide(client)
    env["SPY_KEY"] = "k1"
    decide(client)
    assert seen == ["", "k1"]


def test_raw_default_off_client_on_call_override():
    r0 = decide(create_client(adapters=[fake_provider({JEV.id: [OK]})]))
    assert not r0.envelope.raw  # ABSENT
    c = create_client(adapters=[fake_provider({JEV.id: [OK, OK]})], raw=True)
    a, b = decide(c), decide(c, raw=False)
    assert a.envelope.raw["answers"] == OK["body"]["answers"] and not b.envelope.raw


def test_decide_or_throw_raises_the_urim_error():
    c = create_client(adapters=[fake_provider({JEV.id: [{"fail": "auth"}]})])
    with pytest.raises(UrimError) as e:
        run(c.decide_or_throw(TRIAGE, INPUT))
    assert e.value.type == "auth"


def test_explain_uses_client_budget_and_prices_and_unknown_never_skips():
    c = create_client(adapters=[], prices=PRICES, budget=Budget(0.002, "USD"))
    assert c.explain(TRIAGE).steps[0].action == "skip"
    plain = create_client(adapters=[], budget=Budget(0.0, "USD"))
    assert [s.action for s in plain.explain(TRIAGE, input=INPUT).steps] == ["call", "call"]  # no prices: unknown


# --- D11 ---
def test_interpret_value_and_rethrow():
    c = create_client(adapters=[fake_provider({JEV.id: [OK, OK]})])
    d = dataclasses.replace(TRIAGE, interpret=lambda answers, cut: (answers["team"].value, cut["auto_route"].passes))
    r = decide(c, d)
    assert r.value == (r.envelope.answers["team"].value, r.thresholds["auto_route"].passes)
    boom = TypeError("bug in interpret")
    seen = []

    def bad(answers, cut):
        raise boom

    fake = fake_provider({JEV.id: [OK], CLEF.id: [OK]})
    c2 = create_client(adapters=[fake], on_settled=seen.append)
    with pytest.raises(TypeError) as e:
        decide(c2, dataclasses.replace(TRIAGE, interpret=bad))
    assert e.value is boom and len(fake.calls) == 1
    assert seen[0].outcome == "interpret_failed" and seen[0].envelope.interpret_failed is True


# --- D3 hooks ---
def test_on_settled_gets_frozen_record_with_the_result_envelope():
    seen = []
    r = decide(create_client(adapters=[fake_provider({JEV.id: [OK]})], on_settled=seen.append))
    assert isinstance(seen[0], Settled) and seen[0].envelope is r.envelope and seen[0].error is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        seen[0].outcome = "abstain"  # type: ignore[misc]


def test_hook_error_goes_to_on_hook_error_with_record_never_to_caller():
    got = []

    def hook(s):
        raise RuntimeError("telemetry down")

    r = decide(
        create_client(
            adapters=[fake_provider({JEV.id: [{"fail": "auth"}]})],
            on_settled=hook,
            on_hook_error=lambda err, s: got.append((err, s)),
        )
    )
    assert not r.ok and len(got) == 1 and got[0][1].outcome == "abstain"


def test_default_hook_error_warns_once(caplog):
    def hook(s):
        raise RuntimeError("telemetry down")

    c = create_client(adapters=[fake_provider({JEV.id: [OK, OK]})], on_settled=hook)
    with caplog.at_level(logging.WARNING, logger="urim"):
        decide(c)
        decide(c)
    assert [r.getMessage() for r in caplog.records] == ["urim: on_settled failed: telemetry down"]


def test_hooks_are_fire_and_forget_and_flush_awaits_async_hooks():
    state = {"done": False}

    async def hook(s):
        await asyncio.sleep(0.01)
        state["done"] = True

    async def go():
        c = create_client(adapters=[fake_provider({JEV.id: [OK]})], on_settled=hook)
        await c.decide(TRIAGE, INPUT)
        before = state["done"]
        await c.flush()
        return before, state["done"]

    assert run(go()) == (False, True)


def test_settled_record_key_set_is_uniform():
    from urim.boundary import to_json

    seen = []
    decide(create_client(adapters=[fake_provider({JEV.id: [OK]})], on_settled=seen.append))
    decide(create_client(adapters=[fake_provider({JEV.id: [{"fail": "auth"}]})], on_settled=seen.append))
    assert sorted(to_json(seen[0])) == sorted(to_json(seen[1]))
