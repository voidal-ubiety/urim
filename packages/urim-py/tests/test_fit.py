"""run_fit / parse_cases / estimate_fit_cost against urim-ts runFit outputs (shared-fixtures/fit.vectors.json)."""

import asyncio

import pytest
from conftest import FIXED_NOW_MS, GATE, PRICES, SHARED, STRICT_GATE, load

from urim.boundary import parse_price_table, to_json
from urim.fit import estimate_fit_cost, parse_cases, run_fit
from urim.lock import serialize_lock
from urim.testing import fake_provider

V = load(SHARED / "fit.vectors.json")["run"]
DEFS = {"gate": GATE, "strict": STRICT_GATE}


def test_parse_cases_matches_ts():
    text = (SHARED.parent / "urim-ts" / "test" / "fixtures" / "eval.fit.jsonl").read_text("utf-8")
    assert to_json(parse_cases(text)) == V["cases"]
    with pytest.raises(ValueError):
        parse_cases('{"labels": {}}\n')


def test_estimate_matches_ts():
    assert to_json(estimate_fit_cost(GATE, 5, 2, PRICES)) == V["estimate"]


@pytest.mark.parametrize("v", V["runs"], ids=[v["name"] for v in V["runs"]])
def test_run_fit_matches_ts(v):
    fake = fake_provider(V["script"], cycle=True)
    out = asyncio.run(
        run_fit(
            DEFS[v["def"]],
            parse_cases_from(V["cases"]),
            adapters=[fake],
            prices=parse_price_table(v["prices"]),
            repeat=v["repeat"],
            yes=v["yes"],
            now=lambda: FIXED_NOW_MS,
        )
    )
    assert to_json(out) == v["expected"]
    if v["lockText"] is not None:
        assert serialize_lock(out.lock) == v["lockText"]
    if not v["yes"]:
        assert fake.calls == []


def parse_cases_from(cases):
    import json

    return parse_cases("\n".join(json.dumps(c) for c in cases))
