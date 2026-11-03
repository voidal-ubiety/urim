"""Release metadata: the PyPI distribution and the import package are both `urim`."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_distribution_name_is_urim() -> None:
    assert tomllib.loads(PYPROJECT.read_text())["project"]["name"] == "urim"


def test_console_script_is_urim() -> None:
    assert tomllib.loads(PYPROJECT.read_text())["project"]["scripts"] == {"urim": "urim.cli:main"}


def test_release_metadata() -> None:
    meta = tomllib.loads(PYPROJECT.read_text())
    project = meta["project"]
    assert project["version"] == "0.0.1"
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    assert project["urls"]["Repository"] == "https://github.com/voidal-ubiety/urim"
    assert project["dependencies"] == []
    assert meta["build-system"]["build-backend"] == "setuptools.build_meta"


def test_license_files_match_repository_root() -> None:
    here = PYPROJECT.parent
    for name in ("LICENSE", "NOTICE"):
        assert (here / name).read_text() == (here.parents[1] / name).read_text()
