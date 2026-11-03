"""A real-file module for the `urim` console smoke test: the fit gate from urim-ts test/fixtures/fit.decision.ts."""

from urim import Issue, Objective, define_decision, json_schema_adapter, noul, threshold, tier

__all__ = ["gate"]

_JEV = tier(
    provider="fake-systemone",
    model="jev",
    version="1.14.0",
    camp="systemone",
    question_types=["noul", "choice", "score"],
)
_CLEF = tier(
    provider="cloudflare", model="clef-flash", version="x.y.z", camp="systemone", question_types=["noul", "choice"]
)
_INPUT = json_schema_adapter(
    {"type": "object", "properties": {"report": {"type": "string"}}, "required": ["report"]},
    lambda v: [] if isinstance(v, dict) and isinstance(v.get("report"), str) else [Issue("report", "expected string")],
)

gate = define_decision(
    contract="fit-gate@1.0.0",
    tiers=[_JEV, _CLEF],
    input=_INPUT,
    questions={"page": noul("Page?", yes="y", no="n")},
    failover_on=[],
    thresholds={"gate": threshold(on="page", objective=Objective(min_precision=0.75))},
)
