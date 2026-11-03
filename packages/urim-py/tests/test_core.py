import dataclasses

import pytest
from conftest import CLEF, JEV, OPENAI, PRICES, PRICES_JSON, SEVERITY, TRIAGE

from urim import (
    UrimError,
    choice,
    define_decision,
    encode_request,
    estimate_input_tokens,
    explain,
    next_step,
    noul,
    plan_attempts,
    pydantic_schema,
    read_envelope,
    resolve_cuts,
    threshold,
)
from urim.boundary import parse_price_table
from urim.types import Answer, Budget, ContractRef, Lock

INPUT = {"report": "db down"}


def test_plan_per_call_skip_and_unknown_never_skipped():
    p = plan_attempts(TRIAGE, budget=Budget(0.002, "USD"), prices=PRICES)
    assert [(s.action, s.cost_source, s.reason) for s in p.steps] == [
        ("skip", "per_call", "budget"),
        ("call", "per_call", None),
    ]
    q = plan_attempts(TRIAGE, budget=Budget(0.002, "USD"), prices=parse_price_table({**PRICES_JSON, "entries": {}}))
    assert [s.action for s in q.steps] == ["call", "call"]


def test_pre_call_token_estimate_formula():
    prices = parse_price_table({**PRICES_JSON, "entries": {OPENAI.id: {"perMInputTokens": 1000, "currency": "USD"}}})
    tokens = estimate_input_tokens(encode_request(SEVERITY, OPENAI, INPUT))
    step = explain(SEVERITY, budget=Budget(1, "USD"), prices=prices, input=INPUT).steps[0]
    assert (step.estimated_input_tokens, step.cost_source, step.estimated_cost) == (
        tokens,
        "estimated_pre_call",
        tokens * 1000 / 1e6,
    )
    assert step.action == ("skip" if tokens * 1000 / 1e6 > 1 else "call")
    no_input = explain(SEVERITY, budget=Budget(1, "USD"), prices=prices).steps[0]
    assert (no_input.cost_source, no_input.action) == (None, "call")


def test_currency_mismatch_is_unknown():
    assert plan_attempts(TRIAGE, budget=Budget(0.001, "EUR"), prices=PRICES).steps[0].action == "call"


def test_next_step():
    assert next_step(TRIAGE, "timeout") == "next"
    assert next_step(TRIAGE, "refused") == "abstain"
    assert next_step(SEVERITY, "rate_limited") == "abstain"


def _ans(c):
    return {"page": Answer("yes", c, "urim_derived", {}), "team": Answer("data", c, "native", {})}


def test_cuts_default_lock_none_and_missing_confidence():
    cuts = resolve_cuts(TRIAGE, JEV, _ans(0.7))
    assert (cuts["page_oncall"].source, cuts["page_oncall"].passes) == ("default", False)
    assert (cuts["auto_route"].source, cuts["auto_route"].passes) == ("none", True)
    locked = resolve_cuts(
        TRIAGE, JEV, _ans(0.7), lock=Lock(ContractRef("c", "sha256:h"), {"auto_route": {JEV.id: 0.6}})
    )
    assert locked["auto_route"].source == "lock"
    assert resolve_cuts(TRIAGE, JEV, _ans(None))["page_oncall"].passes is False
    with pytest.raises(UrimError) as e:
        resolve_cuts(TRIAGE, JEV, _ans(0.9), mode="prod")
    assert e.value.type == "lock_violation"


def test_define_rejects_bad_definitions_as_values():
    with pytest.raises(UrimError) as e:
        define_decision(
            contract="x@1",
            tiers=[CLEF, CLEF],
            input=TRIAGE.input,
            questions={"s": noul("?", yes="y", no="n")},
            failover_on=["refused"],
            thresholds={"t": threshold(on="missing")},
        )
    assert e.value.type == "invalid_definition" and len(e.value.issues) >= 3


def test_frozen_data():
    with pytest.raises(TypeError):
        TRIAGE.questions["x"] = choice("?", {"a": "a", "b": "b"})  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        JEV.id = "other"  # type: ignore[misc]


def test_read_envelope_rejects_bad_confidence_source():
    ok, issues = read_envelope({"envelope": "urim/2"})
    assert not ok and any(i.path == "envelope" for i in issues)


def test_pydantic_adapter():
    pydantic = pytest.importorskip("pydantic")

    class In(pydantic.BaseModel):
        report: str

    a = pydantic_schema(In)
    assert a.parse({"report": "x"}).value == {"report": "x"}
    assert a.parse({}).ok is False
    assert a.to_json_schema()["required"] == ["report"]
