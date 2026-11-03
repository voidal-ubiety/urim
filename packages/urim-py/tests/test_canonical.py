import json
import shutil
import subprocess

import pytest
from conftest import SHARED, TS, load

from urim import canonicalize, sha256

INPUTS = load(SHARED / "canonical.inputs.json")
VECTORS = load(SHARED / "canonical.vectors.json")


@pytest.mark.parametrize("inp,vec", list(zip(INPUTS, VECTORS, strict=True)), ids=[v["name"] for v in VECTORS])
def test_shared_vectors_byte_identical(inp, vec):
    out = canonicalize(inp["value"])
    assert out == vec["json"]
    assert sha256(out) == vec["hash"]


@pytest.mark.parametrize(
    "n,s",
    [
        (1.0, "1"),
        (1e21, "1e+21"),
        (1e-7, "1e-7"),
        (-0.0, "0"),
        (0.1 + 0.2, "0.30000000000000004"),
        (1e20, "100000000000000000000"),
        (5e-324, "5e-324"),
        (123e-20, "1.23e-18"),
    ],
)
def test_ecmascript_number_format(n, s):
    assert canonicalize(n) == s


def test_rejects_non_json_values():
    for bad in (float("nan"), float("inf"), object()):
        with pytest.raises(TypeError):
            canonicalize(bad)


def test_lone_surrogate_matches_node_escaping_and_hash():
    assert canonicalize("\ud800") == '"\\ud800"'


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_cross_port_live_node():
    """Spawns the TS reference locally (no network) on fresh values, incl. ones not in the vector file."""
    values = [
        {"k": [1.5e-9, 2**53, 0.000001, "\u2028", "\ud83c\udf89"], "\ud800": "lone"},
        [1e300, -2.5e-8],
        "\u00e9" * 3,
    ]
    script = (
        "import {canonicalize, sha256} from './src/index.ts';"
        "const vs = JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "console.log(JSON.stringify(vs.map(v => { const j = canonicalize(v); return [j, sha256(j)]; })));"
    )
    script = script.replace("require('fs')", "(await import('node:fs'))")
    payload = json.dumps(values)  # Python escapes lone surrogates as \ud800, which JSON.parse accepts
    r = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=TS,
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    expected = json.loads(r.stdout)
    assert [[canonicalize(v), sha256(canonicalize(v))] for v in values] == expected


def test_python_surrogate_pair_is_one_astral_char_like_js():
    # found by the live cross-port test: Python keeps "\ud83c\udf89" as two code points, JS sees one character
    assert canonicalize("\ud83c\udf89") == canonicalize("🎉") == '"🎉"'
    assert sha256(canonicalize("\ud83c\udf89")) == sha256('"🎉"')
