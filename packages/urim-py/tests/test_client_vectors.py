"""Client decide loop vs urim-ts createClient on shared scenarios (shared-fixtures/client.vectors.json).

The result, the envelope and every Settled record must serialize to exactly the JSON urim-ts produced.
"""

import asyncio

import pytest
from conftest import DEFS, FIXED_NOW_MS, PRICES, SHARED, load

from urim.boundary import from_json, to_json
from urim.client import create_client
from urim.testing import fake_provider
from urim.types import Budget, Lock

V = load(SHARED / "client.vectors.json")


def run(v):
    d = DEFS[v["def"]]
    deps = v.get("deps") or {}
    opts = v.get("opts") or {}
    settled = []
    fake = fake_provider(v["script"])
    client = create_client(
        adapters=[fake],
        now=lambda: FIXED_NOW_MS,
        on_settled=settled.append,
        mode=deps.get("mode", "dev"),
        decisions=[d] if "mode" in deps else (),
        locks=[from_json(Lock, v["lock"])] if v["lock"] else (),
        prices=PRICES if deps.get("prices") else None,
        budget=from_json(Budget, deps["budget"]) if "budget" in deps else None,
        raw=deps.get("raw", False),
        deadline_ms=deps.get("deadlineMs"),
    )

    async def go():
        kw = {}
        if "raw" in opts:
            kw["raw"] = opts["raw"]
        if "budget" in opts:
            kw["budget"] = from_json(Budget, opts["budget"])
        if "deadlineMs" in opts:
            kw["deadline_ms"] = opts["deadlineMs"]
        r = await client.decide(d, v["input"], **kw)
        await client.flush()
        return r

    return asyncio.run(go()), settled, fake


def as_json(r):
    if r.ok:
        return {
            "ok": True,
            "value": to_json(r.value),
            "envelope": to_json(r.envelope),
            "fallback": to_json(r.fallback),
            "thresholds": to_json(r.thresholds),
        }
    return {"ok": False, "error": {"type": r.error.type, "tier": r.error.tier}, "attempts": to_json(r.attempts)}


@pytest.mark.parametrize("v", V, ids=[v["name"] for v in V])
def test_scenario_matches_ts(v):
    r, settled, fake = run(v)
    assert [c.tier_id for c in fake.calls] == v["calls"]
    assert as_json(r) == v["expected"]
    assert to_json(settled) == v["settled"]
