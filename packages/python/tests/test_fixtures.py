import json
import subprocess
import sys
from pathlib import Path

import pytest

from urim import check_file
from urim.cli import main

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["path"] for c in CASES])
def test_shared_case(case):
    path = str(FIXTURES / case["path"])
    result = check_file(path)
    assert result.exit_code == case["exit"]
    assert result.line == case["output"].replace("{file}", path)


def test_cli_streams_and_exit(capsys):
    ok = str(FIXTURES / "valid/minimal.lock")
    assert main(["check", ok]) == 0
    out, err = capsys.readouterr()
    assert out.strip().endswith("ok (lockfile, hoshen 1, urim 0.1)") and err == ""
    bad = str(FIXTURES / "invalid/hoshen-unsupported.lock")
    assert main(["check", bad]) == 1
    out, err = capsys.readouterr()
    assert out == "" and "unsupported hoshen version 2" in err


def test_cli_usage(capsys):
    assert main([]) == 2
    assert main(["--version"]) == 0
    assert "urim 0.0.1" in capsys.readouterr().out


def test_module_entry():
    proc = subprocess.run([sys.executable, "-m", "urim", "--version"], capture_output=True, text=True)
    assert proc.returncode == 0 and proc.stdout.strip() == "urim 0.0.1"
