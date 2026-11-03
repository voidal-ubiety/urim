"""Python vs TS reference: emit, codecs, token estimate, envelope."""

import pytest
from conftest import DEFS, JEV, PRICES, SHARED, TIERS, TRIAGE, TS, load

from urim import (
    DESCRIPTORS,
    build_envelope,
    decode_reply,
    emit,
    encode_request,
    estimate_input_tokens,
    read_envelope,
    resolve_cuts,
)
from urim.boundary import to_json
from urim.camps import DecodedOk
from urim.types import Attempt, WireReply

CODEC = load(SHARED / "codec.vectors.json")


def test_emit_triage_matches_ts_golden():
    golden = load(TS / "test/golden/triage.emit.json")
    out = emit(TRIAGE)
    assert out.json == golden["json"] and out.hash == golden["hash"]


@pytest.mark.parametrize("name", ["triage", "severity"])
def test_contract_hashes_match_ts(name):
    assert emit(DEFS[name]).hash == CODEC["contracts"][name]


@pytest.mark.parametrize("c", CODEC["encode"], ids=lambda c: f"{c['def']}-{c['tier']}")
def test_encode_matches_ts(c):
    req = encode_request(DEFS[c["def"]], TIERS[c["tier"]], c["input"])
    assert (req.url, req.path, req.body) == (c["url"], c["path"], c["body"])
    assert estimate_input_tokens(req) == c["estimatedInputTokens"]


def _plain(decoded):
    if isinstance(decoded, DecodedOk):
        u = decoded.usage
        return {
            "ok": True,
            "answers": to_json(dict(decoded.answers)),
            "usage": None if u is None else {"inputTokens": u.input_tokens, "outputTokens": u.output_tokens},
            "model": decoded.model,
        }
    e = decoded.error
    return {"ok": False, "type": e.type, "requestId": e.request_id, "retryAfterMs": e.retry_after_ms}


@pytest.mark.parametrize("c", CODEC["decode"], ids=lambda c: c["name"])
def test_decode_matches_ts(c):
    reply = WireReply(c.get("status", 200), c.get("headers", {}), c["body"])
    got = _plain(decode_reply(DEFS[c["def"]], TIERS[c["tier"]], reply))
    exp = dict(c["expected"])
    if exp["ok"] and exp.get("usage") is not None:
        u = exp["usage"]
        exp["usage"] = {
            "inputTokens": u.get("inputTokens", u.get("input_tokens")),
            "outputTokens": u.get("outputTokens", u.get("output_tokens")),
        }
    exp.setdefault("model", None) if exp["ok"] else None
    assert got == exp


def test_envelope_matches_ts_golden():
    golden = load(TS / "test/golden/envelope.v1.example.json")
    ok = next(c for c in CODEC["decode"] if c["name"] == "systemone triage ok")
    d = decode_reply(TRIAGE, JEV, WireReply(200, {}, ok["body"]))
    assert isinstance(d, DecodedOk)
    env = build_envelope(
        d=TRIAGE,
        contract_hash=emit(TRIAGE).hash,
        tier=JEV,
        answers=d.answers,
        cuts=resolve_cuts(TRIAGE, JEV, d.answers),
        attempts=[Attempt(JEV.id, "ok", 0)],
        request_ids={},
        at="2026-10-28T21:00:00.000Z",
        prices=PRICES,
        usage=d.usage,
    )
    assert to_json(env) == golden
    assert read_envelope(to_json(env)) == (True, [])


def test_descriptor_table_rows_match_ts_source():
    src = (TS / "src/descriptors.ts").read_text("utf-8")
    for provider, desc in DESCRIPTORS.items():
        assert desc.url in src, provider
