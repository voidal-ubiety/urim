"""C-098: the golden RFC 8785 corpus, shared with the JS and Rust ports."""

import json
from pathlib import Path

import pytest

from urim.jcs import canonical
from urim.problem import NON_FINITE, Failure
from urim.profile import parse_document

CORPUS = json.loads((Path(__file__).parents[3] / "fixtures/jcs/corpus.json").read_text(encoding="utf-8"))[
    "cases"
]


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_c098_golden_corpus(case: dict[str, str]) -> None:
    value = parse_document(case["yaml"] + "\n")
    if "jcs" in case:
        assert canonical(value) == case["jcs"]
    else:
        with pytest.raises(Failure) as info:
            canonical(value)
        assert info.value.args == (NON_FINITE,)


def test_c098_only_json_values() -> None:
    with pytest.raises(TypeError):
        canonical(object())
