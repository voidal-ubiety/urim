"""scripts/check-internal-paths fails exactly when something under drafts/ or research/ is tracked."""

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check-internal-paths"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("public\n")
    git(tmp_path, "add", "README.md")
    return tmp_path


def run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), str(repo)], check=False, capture_output=True, text=True
    )


def test_passes_with_no_internal_paths(repo: Path) -> None:
    (repo / "drafts").mkdir()
    (repo / "drafts" / "untracked.md").write_text(
        "x\n"
    )  # present on disk but untracked: fine
    assert run(repo).returncode == 0


@pytest.mark.parametrize("path", ["drafts/NOTE.md", "research/deep/FACTS.md"])
def test_fails_when_an_internal_path_is_tracked(repo: Path, path: str) -> None:
    f = repo / path
    f.parent.mkdir(parents=True)
    f.write_text("internal\n")
    git(repo, "add", "-f", path)
    r = run(repo)
    assert r.returncode == 1
    assert path in r.stderr


def test_a_similar_name_elsewhere_is_not_flagged(repo: Path) -> None:
    f = repo / "docs" / "drafts" / "ok.md"
    f.parent.mkdir(parents=True)
    f.write_text("x\n")
    git(repo, "add", "docs/drafts/ok.md")
    assert run(repo).returncode == 0
