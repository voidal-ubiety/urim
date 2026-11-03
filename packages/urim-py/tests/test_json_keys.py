"""Every JSON key Urim writes is camelCase (mirror of urim-ts test/json-keys.test.ts)."""

import re

from conftest import SEVERITY, SHARED, TRIAGE, TS, load

from urim.emit import emit

MAPS = {"questions", "thresholds", "answers", "requestIds", "perTier", "cutoffs", "properties", "labels"}
OPAQUE = {"cuts", "native", "raw", "input", "script", "body"}  # cuts: threshold -> tier -> number, user names only
CAMEL = re.compile(r"^[a-z][a-zA-Z0-9]*$")


def snake_keys(v, path="$"):
    if isinstance(v, list):
        return [k for i, x in enumerate(v) for k in snake_keys(x, f"{path}[{i}]")]
    if not isinstance(v, dict):
        return []
    out = []
    for k, x in v.items():
        if k in OPAQUE:
            continue
        if not CAMEL.match(k):
            out.append(f"{path}.{k}")
        if k in MAPS or (k == "tiers" and isinstance(x, dict)):
            out += [s for mk, mx in x.items() for s in snake_keys(mx, f"{path}.{k}.{mk}")]
        else:
            out += snake_keys(x, f"{path}.{k}")
    return out


def test_emitted_contracts_are_camel():
    assert [k for d in (TRIAGE, SEVERITY) for k in snake_keys(emit(d).document)] == []


def test_golden_and_shared_vectors_are_camel():
    assert snake_keys(load(TS / "test" / "golden" / "envelope.v1.example.json")) == []
    client = load(SHARED / "client.vectors.json")
    assert [k for v in client for k in snake_keys([v.get("expected"), v.get("settled"), v.get("lock")])] == []
    assert [k for v in load(SHARED / "lock.vectors.json") for k in snake_keys(v["input"])] == []
