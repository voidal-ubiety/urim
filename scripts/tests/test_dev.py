"""scripts/dev: help, unknown commands and subcommand dispatch (DEV_DRY_RUN=1 prints instead of running)."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "dev"
SUBCOMMANDS = ["setup", "test", "check", "build", "pack-check", "clean", "help"]


def run(*args: str, dry: bool = True, **env: str) -> subprocess.CompletedProcess[str]:
    full_env = {k: v for k, v in os.environ.items() if k not in ("PYTHONS", "TOOLS")}
    full_env.update(env)
    if dry:
        full_env["DEV_DRY_RUN"] = "1"
    return subprocess.run([str(SCRIPT), *args], check=False, capture_output=True, text=True, env=full_env)


@pytest.mark.parametrize("args", [(), ("help",), ("--help",), ("-h",)])
def test_help_lists_every_subcommand(args: tuple[str, ...]) -> None:
    r = run(*args)
    assert r.returncode == 0
    for sub in SUBCOMMANDS:
        assert sub in r.stdout


def test_unknown_command_fails_with_help() -> None:
    r = run("nope")
    assert r.returncode != 0
    assert "unknown command: nope" in r.stderr
    assert "setup" in r.stdout


def test_test_defaults_to_both_ports() -> None:
    r = run("test")
    assert r.returncode == 0
    assert "pytest" in r.stdout and "npm test" in r.stdout


def test_test_py_only() -> None:
    r = run("test", "py")
    assert "pytest" in r.stdout and "npm test" not in r.stdout


def test_test_ts_only() -> None:
    r = run("test", "ts")
    assert "npm test" in r.stdout and "pytest" not in r.stdout


def test_test_bad_port_fails() -> None:
    assert run("test", "rust").returncode != 0


def test_check_defaults_to_venv() -> None:
    r = run("check")
    assert r.returncode == 0
    assert "PYTHONS=" in r.stdout and ".venv/bin/python" in r.stdout and "packages/check.sh" in r.stdout


def test_check_respects_env_overrides() -> None:
    r = run("check", PYTHONS="/x/py /y/py", TOOLS="/x")
    assert "PYTHONS=/x/py /y/py" in r.stdout and "TOOLS=/x" in r.stdout


def test_setup_installs_all_extras_and_npm_ci() -> None:
    r = run("setup")
    assert r.returncode == 0
    assert "packages/urim-py[dev,pydantic,httpx]" in r.stdout
    assert "npm ci" in r.stdout


def test_build_covers_both_ports() -> None:
    r = run("build")
    assert "npm run build" in r.stdout and "build" in r.stdout and "urim-py" in r.stdout


def test_clean_keeps_venv_unless_all() -> None:
    assert ".venv" not in run("clean").stdout
    assert ".venv" in run("clean", "--all").stdout


def test_clean_rejects_bad_flag() -> None:
    assert run("clean", "--everything").returncode != 0


def test_pack_check_dry_run() -> None:
    r = run("pack-check")
    assert r.returncode == 0
    assert "npm pack" in r.stdout and "wheel" in r.stdout
