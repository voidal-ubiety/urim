"""The README quickstart is the PyPI page's first example: it must run offline exactly as written."""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()


def test_readme_quickstart_runs_offline(tmp_path: Path) -> None:
    m = re.search(r"```python\n(.*?)```", README, re.S)
    assert m, "README needs a ```python quickstart block"
    script = tmp_path / "quickstart.py"
    script.write_text(m.group(1))
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(ROOT / "src")}
    out = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, check=True).stdout
    assert "value='yes'" in out
    assert "confidence=0.9" in out


def test_readme_has_install_line_and_no_internal_notes() -> None:
    assert "pip install urim" in README
    assert not re.search(r"slice \d|Port of the urim-ts", README)
