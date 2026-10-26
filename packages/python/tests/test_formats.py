"""C-096: ``fixtures/formats.json``, the same verdicts as ``formats.ts`` and ``formats.rs``."""

import json
from pathlib import Path
from typing import get_args

import pytest

from urim.formats import matches
from urim.node import Fmt

ROOT = Path(__file__).parents[3]
TABLE = json.loads((ROOT / "fixtures/formats.json").read_text(encoding="utf-8"))["formats"]
CASES = [(fmt, c["value"], c["ok"]) for fmt, cases in TABLE.items() for c in cases]


def test_c096_every_format_is_covered() -> None:
    assert sorted(TABLE) == sorted(get_args(Fmt))


@pytest.mark.parametrize(("fmt", "value", "ok"), CASES)
def test_c096_shared_verdicts(fmt: Fmt, value: str, ok: bool) -> None:  # noqa: FBT001 - a table row
    assert matches(fmt, value) is ok
