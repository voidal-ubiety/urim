"""`urim` CLI parity: every case in shared-fixtures/cli.vectors.json was produced by urim-ts src/cli.ts main()
with an in-memory io and a fixed clock. Same argv + same input files -> same exit code, lines and file bytes."""

import subprocess
import sys

import pytest
from conftest import FIXED_NOW_MS, GATE, ROOT, SEVERITY, SHARED, STRICT_GATE, TRIAGE, load

from urim.cli import main
from urim.emit import emit

V = load(SHARED / "cli.vectors.json")
NOT_A_DECISION = {"hello": "world"}
MODULES = {
    "defs": {"triage": TRIAGE, "severity": SEVERITY},
    "gate": {"gate": GATE, "notADecision": NOT_A_DECISION},
    "strict": {"strict": STRICT_GATE},
    "empty": {"notADecision": NOT_A_DECISION},
}


class MemIo:
    def __init__(self, files):
        self.files, self.stdout, self.stderr = dict(files), [], []

    def read_text(self, path):
        if path not in self.files:
            raise FileNotFoundError(f"ENOENT {path}")
        return self.files[path]

    def write_text(self, path, text):
        self.files[path] = text

    def exists(self, path):
        return path in self.files

    def import_module(self, path):
        return MODULES.get(path, {})

    def out(self, line):
        self.stdout.append(line)

    def err(self, line):
        self.stderr.append(line)

    def now(self):
        return FIXED_NOW_MS


@pytest.mark.parametrize("case", V["cases"], ids=[c["name"] for c in V["cases"]])
def test_cli_matches_ts(case):
    io = MemIo({**V["inputs"], **case["preset"]})
    assert main(case["argv"], io) == case["exit"]
    assert io.stdout == case["stdout"]
    assert io.stderr == case["stderr"]
    written = {k: v for k, v in io.files.items() if V["inputs"].get(k) != v and case["preset"].get(k) != v}
    assert written == case["written"]


def test_providers_to_a_py_file_writes_a_python_module(tmp_path):
    io = MemIo(V["inputs"])
    assert main(["providers", "--registry", "registry.json", "--out", "gen/providers.py"], io) == 0
    ns: dict = {}
    exec(compile(io.files["gen/providers.py"], "providers.py", "exec"), ns)
    assert ns["FakeSystemOne"].Jev_1_14_0.id == "fake-systemone/jev@1.14.0"
    assert ns["OpenAI"].Gpt6Luna_0_0_0.camp == "decisions"


def test_console_entry_point_emits_from_a_real_file(tmp_path):
    mod = ROOT / "tests" / "fixtures" / "cli_gate.py"
    r = subprocess.run(
        [sys.executable, "-m", "urim", "emit", str(mod), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout == f"wrote {tmp_path}/fit-gate_1.0.0.contract.json {emit(GATE).hash}\n"
    assert (tmp_path / "urim.hashes.json").exists()


def test_console_fit_without_yes_exits_2(tmp_path):
    ts = ROOT.parent / "urim-ts" / "test" / "fixtures"
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "urim",
            "fit",
            str(ROOT / "tests" / "fixtures" / "cli_gate.py"),
            "--cases",
            str(ts / "eval.fit.jsonl"),
            "--fake",
            str(ts / "fake.fit.json"),
            "--lock",
            str(tmp_path / "l.json"),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert r.returncode == 2 and r.stdout.endswith("refusing to call providers without --yes\n")
    assert not (tmp_path / "l.json").exists()


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_console_help_prints_usage_and_exits_0(flag):
    r = subprocess.run([sys.executable, "-m", "urim", flag], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("usage:\n  urim emit ")
    assert r.stderr == ""
