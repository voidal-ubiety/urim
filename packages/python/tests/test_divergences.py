"""D-008..D-011: pinned Python behavior for known cross-language divergences."""

from __future__ import annotations

from typing import Any

import pytest

from urim import check_file

from .conftest import DIVERGENCES, FIXTURES


@pytest.mark.parametrize(("did", "cases"), DIVERGENCES.items(), ids=list(DIVERGENCES))
def test_pinned_python_behavior(did: str, cases: list[dict[str, Any]]) -> None:
    for case in cases:
        path = str(FIXTURES / case["path"])
        expect = case["expect"]["python"]
        result = check_file(path)
        assert result.exit_code == expect["exit"], (did, case["path"])
        assert result.line == expect["output"].replace("{file}", path), (did, case["path"])
