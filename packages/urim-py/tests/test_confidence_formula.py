"""Confidence naming (pre-0.0.1), mirroring urim-ts test/confidence-formula.test.ts."""

from conftest import JEV, OPENAI, SEVERITY, TRIAGE, TS, load

from urim import CONFIDENCE_RULE, DESCRIPTORS, decode_reply, emit, read_envelope
from urim.camps import systemone
from urim.camps.shared import vendor_confidence
from urim.fit_math import Scored, escalation_at
from urim.types import WireReply


def _reply(body):
    return WireReply(200, {}, body, 1)


def _s1(team_conf, team_probs):
    return {
        "answers": {
            "page": {"type": "noul", "noul": 0.95},
            "team": {"type": "choice", "choice": "data", "confidence": team_conf, "probabilities": team_probs},
        },
        "usage": {"input_tokens": 1200, "output_tokens": 3},
    }


def test_definition_confidence_names_the_formula_per_question_type():
    want = {"noul": "typesafe_normalized", "choice": "vendor_unspecified", "score": "vendor_unspecified"}
    assert dict(TRIAGE.confidence) == want == dict(CONFIDENCE_RULE)
    assert emit(TRIAGE).document["confidence"] == want


def test_answers_carry_confidence_formula():
    r = decode_reply(TRIAGE, JEV, _reply(_s1(0.6, {"data": 0.8, "billing": 0.2})))
    assert r.ok
    assert r.answers["page"].confidence == 0.9
    assert r.answers["page"].confidence_formula == "typesafe_normalized"
    assert r.answers["team"].confidence_formula == "vendor_unspecified"
    o = decode_reply(
        SEVERITY,
        OPENAI,
        _reply({"model": "gpt-6-luna", "answers": [{"type": "predicate", "name": "page", "probability": 0.8}]}),
    )
    assert not o.ok or o.answers["page"].confidence_formula == "typesafe_normalized"


def test_null_confidence_has_null_formula():
    r = decode_reply(TRIAGE, JEV, _reply(_s1(7, {"data": 1})))
    assert r.ok and r.answers["team"].confidence is None and r.answers["team"].confidence_formula is None


def test_no_shipped_descriptor_sets_the_sentinel_and_a_real_zero_stays_zero():
    assert all(not d.confidence_unavailable_sentinel for d in DESCRIPTORS.values())
    r = decode_reply(TRIAGE, JEV, _reply(_s1(0, {})))
    assert r.ok and r.answers["team"].confidence == 0 and r.answers["team"].confidence_source == "native"


def test_sentinel_flag_reads_zero_with_empty_probabilities_as_null():
    s = systemone.decode(TRIAGE, JEV, _s1(0, {}), unavailable_sentinel=True)
    assert s.ok
    t = s.answers["team"]
    assert (t.confidence, t.confidence_source, t.confidence_formula) == (None, None, None)
    assert t.native["confidence"] == 0
    assert s.answers["page"].confidence == 0.9
    kept = systemone.decode(TRIAGE, JEV, _s1(0, {"data": 1}), unavailable_sentinel=True)
    assert kept.ok and kept.answers["team"].confidence == 0
    assert vendor_confidence({"confidence": 0, "probabilities": []}, True) is None
    assert vendor_confidence({"confidence": 0}, True) == 0
    assert vendor_confidence({"confidence": 0, "probabilities": []}, False) == 0


def test_fit_flags_sentinel_answers_as_escalated():
    assert escalation_at([Scored(None, True), Scored(0, True)], 0) == 0.5


def test_envelope_confidence_formula_is_optional_and_closed():
    golden = load(TS / "test/golden/envelope.v1.example.json")
    assert golden["answers"]["page"]["confidenceFormula"] == "typesafe_normalized"
    strip = {k: {kk: vv for kk, vv in v.items() if kk != "confidenceFormula"} for k, v in golden["answers"].items()}
    assert read_envelope({**golden, "answers": strip})[0]
    bad = {**golden["answers"], "page": {**golden["answers"]["page"], "confidenceFormula": "top_probability"}}
    assert not read_envelope({**golden, "answers": bad})[0]
