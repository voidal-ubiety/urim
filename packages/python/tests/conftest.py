"""Shared fixtures for the contract suite. See CONTRACT.md for the meaning of each ID."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def load_cases(name: str) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))["cases"]
    return cases


def by_id(cases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        groups[case["id"]].append(case)
    return dict(groups)


FILE_CASES = by_id(load_cases("cases.json"))
CLI_CASES = by_id(load_cases("cli.json"))
DIVERGENCES = by_id(load_cases("divergences.json"))
