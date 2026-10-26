"""C-070..C-072: the library API exported from the package root."""

from __future__ import annotations

import re

import urim
from urim.check import check_text

from .conftest import PACKAGE_ROOT


def test_c070_check_text_uses_file_only_in_the_message() -> None:
    result = check_text("no/such/file.lock", 'hoshen: 1\nurim: "0.1"\n')
    assert result == urim.CheckResult(True, "no/such/file.lock: ok (lockfile, hoshen 1, urim 0.1)")
    assert check_text("", "\ufeffhoshen: 1\nurim: x\n").line == ": ok (lockfile, hoshen 1, urim x)"


def test_c071_result_carries_ok_line_and_exit_code() -> None:
    bad = check_text("f", "[]")
    assert (bad.ok, bad.line, bad.exit_code) == (False, "f: error: root must be a mapping", 1)
    missing = urim.check_file("definitely/missing")
    expected = (False, "definitely/missing: error: cannot read file", 1)
    assert (missing.ok, missing.line, missing.exit_code) == expected


def test_c072_supported_hoshen_and_version() -> None:
    assert set(urim.SUPPORTED_HOSHEN) == {1}
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None
    assert urim.__version__ == match.group(1)
