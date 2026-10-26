"""C-010..C-060: every shared file case, one test per contract ID (fixtures/cases.json)."""

from __future__ import annotations

from typing import Any

import pytest

from urim import check_file

from .conftest import FILE_CASES, FIXTURES


@pytest.mark.parametrize(("cid", "cases"), FILE_CASES.items(), ids=list(FILE_CASES))
def test_shared_file_cases(cid: str, cases: list[dict[str, Any]]) -> None:
    for case in cases:
        path = str(FIXTURES / case["path"])
        result = check_file(path)
        assert result.exit_code == case["exit"], (cid, case["path"])
        assert result.ok is (case["exit"] == 0), (cid, case["path"])
        assert result.line == case["output"].replace("{file}", path), (cid, case["path"])


def test_c000_every_case_has_a_contract_id() -> None:
    for cid in FILE_CASES:
        assert cid.startswith("C-") and len(cid) == 5 and cid[2:].isdigit()
