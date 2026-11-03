"""Python mirrors of urim-ts test/fixtures.ts. emit-hash parity proves they are the same definitions."""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SHARED = ROOT.parent / "shared-fixtures"
TS = ROOT.parent / "urim-ts"

from fake_systemone import FAKE_PROVIDER  # noqa: E402

from urim import Objective, choice, define_decision, json_schema_adapter, noul, score, threshold, tier  # noqa: E402
from urim.errors import Issue  # noqa: E402


def load(path: pathlib.Path):
    return json.loads(path.read_text("utf-8"))


JEV = tier(
    provider=FAKE_PROVIDER, model="jev", version="1.14.0", camp="systemone", question_types=["noul", "choice", "score"]
)
CLEF = tier(
    provider="cloudflare", model="clef-flash", version="x.y.z", camp="systemone", question_types=["noul", "choice"]
)
OPENAI = tier(
    provider="openai", model="gpt-6-luna", version="0.0.0", camp="decisions", question_types=["noul", "choice", "score"]
)
TIERS = {"JEV": JEV, "OPENAI": OPENAI}

INPUT = json_schema_adapter(
    {"type": "object", "required": ["report"], "properties": {"report": {"type": "string"}}},
    lambda v: [] if isinstance(v, dict) and isinstance(v.get("report"), str) else [Issue("report", "expected string")],
)

TRIAGE = define_decision(
    contract="incident-triage@2.0.0",
    tiers=[JEV, CLEF],
    input=INPUT,
    questions={
        "page": noul("Should someone be paged right now?", yes="Active impact", no="No impact"),
        "team": choice(
            "Which team owns this incident?", {"billing": "b", "platform": "p", "identity": "i", "data": "d"}
        ),
    },
    failover_on=["timeout", "provider_unavailable", "rate_limited", "budget"],
    thresholds={
        "page_oncall": threshold(on="page", default=0.8, objective=Objective(min_precision=0.95)),
        "auto_route": threshold(on="team", objective=Objective(escalation_rate=0.15)),
    },
)

SEVERITY = define_decision(
    contract="severity@1.0.0",
    tiers=[OPENAI, JEV],
    input=INPUT,
    questions={
        "sev": score("How severe?", {"low": "l", "mid": "m", "high": "h"}),
        "page": noul("Page?", yes="y", no="n"),
    },
    failover_on=["timeout"],
    thresholds={},
)
DEFS = {"triage": TRIAGE, "severity": SEVERITY}

PRICES_JSON = {
    "id": "fixture-prices",
    "asOf": "2026-10-28",
    "url": "https://example.invalid/PLACEHOLDER",
    "entries": {JEV.id: {"perCall": 0.004, "currency": "USD"}, CLEF.id: {"perCall": 0.001, "currency": "USD"}},
}


from urim.boundary import parse_price_table  # noqa: E402

PRICES = parse_price_table(PRICES_JSON)

GATE = define_decision(
    contract="fit-gate@1.0.0",
    tiers=[JEV, CLEF],
    input=INPUT,
    questions={"page": noul("Page?", yes="y", no="n")},
    failover_on=[],
    thresholds={"gate": threshold(on="page", objective=Objective(min_precision=0.75))},
)
STRICT_GATE = define_decision(
    contract="fit-gate@1.0.0",
    tiers=[JEV, CLEF],
    input=INPUT,
    questions={"page": noul("Page?", yes="y", no="n")},
    failover_on=[],
    thresholds={"gate": threshold(on="page", objective=Objective(min_precision=1.01))},
)
FIXED_NOW_MS = 1793221200000  # Date.parse("2026-10-28T21:00:00.000Z")
