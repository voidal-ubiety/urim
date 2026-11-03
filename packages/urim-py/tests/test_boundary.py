"""Casing rule (accepted 2026-10-29): JSON is camelCase exactly like urim-ts; the Python API is snake_case;
the mapping lives in ONE module, urim.boundary."""

import dataclasses
import pathlib
import re

from conftest import JEV, PRICES_JSON, TRIAGE, TS, load

import urim
from urim import boundary, build_envelope, decode_reply, emit, resolve_cuts
from urim.types import Answer, Attempt, Envelope, WireReply

SRC = pathlib.Path(urim.__file__).parent
CAMEL = re.compile(r"""["'][a-z]+[A-Z][A-Za-z]*["']""")


def _golden_env():
    ok = next(
        c
        for c in load(TS.parent / "shared-fixtures/codec.vectors.json")["decode"]
        if c["name"] == "systemone triage ok"
    )
    d = decode_reply(TRIAGE, JEV, WireReply(200, {}, ok["body"]))
    prices = boundary.parse_price_table(PRICES_JSON)
    return build_envelope(
        d=TRIAGE,
        contract_hash=emit(TRIAGE).hash,
        tier=JEV,
        answers=d.answers,
        cuts=resolve_cuts(TRIAGE, JEV, d.answers),
        attempts=[Attempt(JEV.id, "ok", 0)],
        request_ids={},
        at="2026-10-28T21:00:00.000Z",
        prices=prices,
        usage=d.usage,
    )


def test_envelope_is_typed_snake_case_and_serializes_to_ts_bytes():
    env = _golden_env()
    assert isinstance(env, Envelope)
    assert env.answers["page"].confidence_source == "urim_derived"
    assert env.tier.question_types == ("noul", "choice", "score")
    assert env.usage.cost.price_table.as_of == "2026-10-28"
    assert env.request_ids == {}
    assert boundary.to_json(env) == load(TS / "test/golden/envelope.v1.example.json")


def test_round_trip_from_json():
    golden = load(TS / "test/golden/envelope.v1.example.json")
    env = boundary.from_json(Envelope, golden)
    assert env.answers["team"].confidence_source == "native"
    assert boundary.to_json(env) == golden


def test_user_keys_are_never_recased():
    a = Answer("yes", 0.5, "native", {"name": "is_urgent", "value": 1, "confidence": 0.5})
    assert boundary.to_json({"is_urgent": a, "someKey": 1}) == {
        "is_urgent": {
            "value": "yes",
            "confidence": 0.5,
            "confidenceSource": "native",
            "native": {"name": "is_urgent", "value": 1, "confidence": 0.5},
        },
        "someKey": 1,
    }


def test_every_member_is_camel_on_the_wire():
    # slice 7: no per-class snake exceptions remain; every JSON key Urim writes is camelCase
    assert boundary.json_name("interpret_failed") == "interpretFailed"
    assert boundary.json_name("set_hash") == "setHash"
    assert boundary.json_name("objectives_met") == "objectivesMet"
    assert boundary.json_name("min_precision") == "minPrecision"
    assert boundary.json_name("from_") == "from"
    assert boundary.json_name("request_ids") == "requestIds"


def test_all_public_dataclass_fields_are_snake_case():
    snake = re.compile(r"^[a-z][a-z0-9_]*$")
    for mod in (urim.types, urim.errors):
        for obj in vars(mod).values():
            if dataclasses.is_dataclass(obj) and isinstance(obj, type):
                for f in dataclasses.fields(obj):
                    assert snake.match(f.name), f"{obj.__name__}.{f.name}"


def test_camel_case_names_live_only_in_the_boundary_module():
    offenders = []
    for p in SRC.rglob("*.py"):
        if p.name == "boundary.py":
            continue
        for n, line in enumerate(p.read_text("utf-8").splitlines(), 1):
            if CAMEL.search(line.split("#")[0]):
                offenders.append(f"{p.relative_to(SRC)}:{n}: {line.strip()}")
    assert offenders == []
