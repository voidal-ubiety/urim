"""C-001..C-007, C-012: the `urim` command line (fixtures/cli.json plus Python-specific checks)."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from urim.cli import main

from .conftest import CLI_CASES, FIXTURES, PACKAGE_ROOT


@pytest.mark.parametrize(("cid", "cases"), CLI_CASES.items(), ids=list(CLI_CASES))
def test_shared_cli_cases(
    cid: str,
    cases: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(FIXTURES)
    for case in cases:
        code = main(case["args"])
        out, err = capsys.readouterr()
        assert (code, out, err) == (case["exit"], case["stdout"], case["stderr"]), (cid, case["args"])


def test_c003_argv_defaults_to_sys_argv(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["urim", "--version"])
    assert main() == 0
    assert capsys.readouterr().out == "urim 0.0.1\n"


@pytest.mark.parametrize("module", ["urim", "urim.cli"])
def test_c007_module_entry_points(
    module: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", [module, "-V"])
    monkeypatch.delitem(sys.modules, module, raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    assert exc.value.code == 0
    assert capsys.readouterr().out == "urim 0.0.1\n"


def test_c007_python_dash_m_subprocess() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "urim", "check", "valid/minimal.lock"],
        capture_output=True,
        text=True,
        cwd=FIXTURES,
        check=False,
    )
    expected = (0, "valid/minimal.lock: ok (lockfile, hoshen 1, urim 0.1)\n", "")
    assert (proc.returncode, proc.stdout, proc.stderr) == expected


def test_c007_console_script_is_declared() -> None:
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'urim = "urim.cli:main"' in pyproject


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="root ignores file modes")
def test_c012_unreadable_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "locked.lock"
    path.write_text('hoshen: 1\nurim: "0.1"\n', encoding="utf-8")
    path.chmod(0)
    try:
        assert main(["check", str(path)]) == 1
        assert capsys.readouterr() == ("", f"{path}: error: cannot read file\n")
    finally:
        path.chmod(0o600)


@pytest.mark.skipif(os.name != "posix", reason="POSIX byte paths only")
def test_d012_non_utf8_path_argument(tmp_path: Path) -> None:
    name = b"f\xff.lock"
    (tmp_path / os.fsdecode(name)).write_bytes(b"hoshen: 1\nurim: x\n")
    r = subprocess.run(
        [sys.executable, "-m", "urim", "check", name], cwd=tmp_path, capture_output=True, check=False
    )
    assert r.returncode == 0
    assert r.stdout.endswith(b": ok (lockfile, hoshen 1, urim x)\n")
