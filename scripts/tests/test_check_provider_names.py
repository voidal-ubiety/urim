"""scripts/check-provider-names fails exactly when the vendor name sits outside the provider-source allowlist."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check-provider-names"
NAME = "Type" + "Safe"  # split so this file does not trip the guard


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), str(repo)], capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    src = tmp_path / "packages/urim-ts/src"
    src.mkdir(parents=True)
    (src / "descriptors.ts").write_text(f"// {NAME} descriptor\n")
    (tmp_path / "README.md").write_text("neutral\n")
    git(tmp_path, "add", ".")
    return tmp_path


def test_allowlisted_provider_source_passes(repo: Path) -> None:
    assert run(repo).returncode == 0


@pytest.mark.parametrize("text", [NAME, NAME.lower(), NAME.upper()])
def test_any_case_outside_allowlist_fails(repo: Path, text: str) -> None:
    t = repo / "packages/urim-ts/test"
    t.mkdir(parents=True)
    (t / "x.test.ts").write_text(f"const p = '{text}';\n")
    git(repo, "add", ".")
    r = run(repo)
    assert r.returncode == 1 and "packages/urim-ts/test/x.test.ts" in r.stderr


def test_public_paths_limits_scope(repo: Path) -> None:
    (repo / "drafts").mkdir()
    (repo / "drafts/notes.md").write_text(f"{NAME}\n")
    (repo / ".public-paths").write_text("# comment\npackages/\nREADME.md\n")
    git(repo, "add", ".")
    assert run(repo).returncode == 0
    (repo / "README.md").write_text(f"{NAME}\n")
    assert run(repo).returncode == 1


def test_untracked_files_are_ignored(repo: Path) -> None:
    (repo / "scratch.txt").write_text(f"{NAME}\n")
    assert run(repo).returncode == 0
