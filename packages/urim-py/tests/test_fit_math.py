"""fit math against vectors generated from urim-ts src/fit-math.ts (exact float equality)."""

import pytest
from conftest import SHARED, load

from urim.boundary import from_json, to_json
from urim.fit_math import Scored, accuracy, brier, escalation_at, fit_cutoff, flip_rate, percentile, precision_at, stdev
from urim.types import Objective

V = load(SHARED / "fit.vectors.json")["math"]


def scored(xs):
    return [Scored(x["confidence"], x["correct"]) for x in xs]


@pytest.mark.parametrize("v", V["fitCutoff"], ids=[f"{v['name']}:{v['objective']}" for v in V["fitCutoff"]])
def test_fit_cutoff(v):
    assert to_json(fit_cutoff(scored(v["xs"]), from_json(Objective, v["objective"]))) == v["expected"]


@pytest.mark.parametrize("v", V["stats"], ids=[v["name"] for v in V["stats"]])
def test_stats(v):
    xs = scored(v["xs"])
    assert accuracy(xs) == v["accuracy"]
    assert brier(xs) == v["brier"]
    assert [precision_at(xs, c) for c in (0, 0.5, 0.8, 1)] == v["precisionAt"]
    assert [escalation_at(xs, c) for c in (0, 0.5, 0.8, 1)] == v["escalationAt"]


def test_flip_rate_stdev_percentile():
    for v in V["flipRate"]:
        assert flip_rate(v["runs"]) == v["expected"], v
    for v in V["stdev"]:
        assert stdev(v["xs"]) == v["expected"], v
    for v in V["percentile"]:
        assert percentile(v["xs"], v["p"]) == v["expected"], v
