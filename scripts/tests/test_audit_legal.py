# SPDX-License-Identifier: Apache-2.0
"""Tests for scripts/audit-legal. Run: python3 -m unittest discover -s scripts/tests"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = importlib.machinery.SourceFileLoader("audit_legal", str(ROOT / "scripts/audit-legal"))
_spec = importlib.util.spec_from_loader("audit_legal", _loader)
assert _spec is not None
audit = importlib.util.module_from_spec(_spec)
_loader.exec_module(audit)

CLASSIFIER = "License :: OSI Approved :: Apache Software License"
HAVE_TOOL = bool(os.environ.get("PIP_LICENSES")) or shutil.which("uvx") is not None


def fake_env(tmp: Path, name: str, metadata_lines: list[str]) -> Path:
    """A venv holding one installed distribution whose METADATA is exactly `metadata_lines`."""
    env = tmp / "env"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(env)], check=True)
    py = env / "bin/python"
    purelib = subprocess.run([str(py), "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])"],
                             capture_output=True, text=True, check=True).stdout.strip()
    dist = Path(purelib) / f"{name}-1.0.dist-info"
    dist.mkdir(parents=True)
    (dist / "METADATA").write_text(
        "\n".join(["Metadata-Version: 2.1", f"Name: {name}", "Version: 1.0", *metadata_lines]) + "\n")
    return py


class PolicyTest(unittest.TestCase):
    def test_python_allow_lists_the_apache_trove_classifier(self) -> None:
        self.assertIn("Apache Software License", audit.python_allow_string(audit.policy()).split(";"))


@unittest.skipUnless(HAVE_TOOL, "needs pip-licenses 5.5.5 (uvx or $PIP_LICENSES)")
class L5PyTest(unittest.TestCase):
    """L5-Py: a package that declares Apache only through its trove classifier
    (as requests does: no License-Expression, classifier 'Apache Software License')."""

    def run_on(self, metadata: list[str], allow: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            py = fake_env(Path(tmp), "classifieronly", metadata)
            return audit.run_pip_licenses(py, ["classifieronly"], allow)

    def test_classifier_only_apache_package_passes(self) -> None:
        r = self.run_on([f"Classifier: {CLASSIFIER}"], audit.python_allow_string(audit.policy()))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Apache Software License", r.stdout)

    def test_it_failed_without_the_classifier_entry(self) -> None:
        # The bug this guards against: SPDX ids alone don't match the classifier name.
        allow = ";".join(a for a in audit.policy()["python_allow"] if a != "Apache Software License")
        r = self.run_on([f"Classifier: {CLASSIFIER}"], allow)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Apache Software License not in allow-only", r.stdout + r.stderr)

    def test_a_gpl_classifier_package_still_fails(self) -> None:
        r = self.run_on(["Classifier: License :: OSI Approved :: GNU General Public License v3 (GPLv3)"],
                        audit.python_allow_string(audit.policy()))
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()


MARK = ("  - mark: \"{m}\"\n    owner: UNVERIFIED\n    kind: tool\n"
        "    allowed_context: nominative\n    forbid_in_package_names: true\n")


class TreeTest(unittest.TestCase):
    """Rules that read the tree, run against a small temporary repo."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.old_root = audit.ROOT
        audit.ROOT = self.tmp
        self.addCleanup(setattr, audit, "ROOT", self.old_root)
        audit.results.clear()
        self.write("config/people.yaml", "security_contact: a@b.dev\ncopyright: x\n")
        self.write("packages/js/package.json", '{"name": "urim"}')
        self.write("packages/python/pyproject.toml", '[project]\nname = "urim"\n')
        self.write("packages/rust/Cargo.toml", '[package]\nname = "urim"\n')

    def write(self, rel: str, text: str) -> None:
        (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.tmp / rel).write_text(text, encoding="utf-8")

    def status(self, rule: str) -> tuple[str, str]:
        r = [x for x in audit.results if x["rule"] == rule][-1]
        return r["status"], r["detail"]

    def test_t1_passes_when_every_used_mark_is_listed(self) -> None:
        self.write("docs/legal/marks.yaml", "marks:\n" + MARK.format(m="Jev"))
        self.write("README.md", "Works with Jev.\n")
        audit.t1()
        self.assertEqual(self.status("T1")[0], "PASS")

    def test_t1_warns_on_an_unlisted_mark(self) -> None:
        self.write("docs/legal/marks.yaml", "marks:\n" + MARK.format(m="Jev"))
        self.write("README.md", "Works with Jev and OpenAI.\n")
        audit.t1()
        self.assertEqual(self.status("T1"), ("WARN", "marks used but not in marks.yaml: OpenAI (README.md)"))

    def test_t1_ignores_a_mark_inside_a_longer_word(self) -> None:
        self.write("docs/legal/marks.yaml", "marks:\n" + MARK.format(m="Jev"))
        self.write("README.md", "Bufferbloat and Rusty things, Pythonic.\n")
        audit.t1()
        self.assertEqual(self.status("T1")[0], "PASS")

    def test_t1_fails_without_marks_yaml_or_with_a_bad_entry(self) -> None:
        audit.t1()
        self.assertEqual(self.status("T1")[0], "FAIL")
        self.write("docs/legal/marks.yaml", "marks:\n  - mark: Jev\n    kind: tool\n")
        audit.t1()
        self.assertIn("missing fields", self.status("T1")[1])

    def test_t4_fails_on_a_mark_in_a_package_name(self) -> None:
        self.write("docs/legal/marks.yaml", "marks:\n" + MARK.format(m="OpenAI"))
        audit.t4()
        self.assertEqual(self.status("T4")[0], "PASS")
        self.write("packages/js/jsr.json", '{"name": "@urim/openai"}')
        audit.t4()
        self.assertEqual(self.status("T4"), ("FAIL", "jsr @urim/openai contains OpenAI"))

    def test_m5_checks_files_and_heading_anchors(self) -> None:
        self.write("CONTRIBUTING.md", "## Dependency policy\n")
        self.write("SECURITY.md", "See [policy](CONTRIBUTING.md#dependency-policy).\n")
        for f in ("packages/rust/deny.toml", "README.md"):
            self.write(f, "")
        audit.m5()
        self.assertEqual(self.status("M5")[0], "PASS")
        self.write("SECURITY.md", "See [policy](CONTRIBUTING.md#dependencies) and [x](docs/gone.md).\n")
        audit.m5()
        self.assertIn("CONTRIBUTING.md#dependencies (no such heading)", self.status("M5")[1])
        self.assertIn("SECURITY.md: docs/gone.md", self.status("M5")[1])

    def test_c4_fails_on_a_promise_word(self) -> None:
        self.write("SECURITY.md", "Mail a@b.dev. There is no response-time commitment.\n")
        audit.c4()
        self.assertEqual(self.status("C4")[0], "PASS")
        self.write("SECURITY.md", "Mail a@b.dev. Sponsors get priority fixes under our SLA.\n")
        audit.c4()
        self.assertEqual(self.status("C4"), ("FAIL", "SECURITY.md makes promises (C1 words): ['SLA', 'priority fix']"))

    def test_c1_flags_funding_wording_outside_the_exempt_legal_docs(self) -> None:
        self.write("docs/legal/RELEASE-CHECKLIST.md", "C1 forbids: early access, SLA.\n")
        self.write("README.md", "Urim checks contracts.\n")
        audit.c1()
        self.assertEqual(self.status("C1")[0], "PASS")
        self.write(".github/FUNDING.yml", "# Sponsors-only builds get early access\n")
        audit.c1()
        self.assertEqual(self.status("C1"), ("FAIL", "funding or promise wording: "
                                             "['.github/FUNDING.yml:1: Sponsors-only', '.github/FUNDING.yml:1: early access']"))

    def test_c3_finds_network_imports_in_each_language(self) -> None:
        self.write("packages/js/src/ok.ts", "import { readFileSync } from 'node:fs';\n")
        self.write("packages/python/src/urim/ok.py", "import json\n")
        self.write("packages/rust/src/ok.rs", "use std::fs;\n")
        audit.c3()
        self.assertEqual(self.status("C3")[0], "PASS")
        self.write("packages/js/src/a.ts", "import https from 'node:https';\nawait fetch(url);\n")
        self.write("packages/python/src/urim/b.py", "import socket\nfrom urllib import request\n")
        self.write("packages/rust/src/c.rs", "use std::net::TcpStream;\n")
        audit.c3()
        self.assertEqual(self.status("C3"), ("FAIL", "network imports in shipped sources: "
                                             "['packages/js/src/a.ts:1', 'packages/js/src/a.ts:2', "
                                             "'packages/python/src/urim/b.py:1', 'packages/python/src/urim/b.py:2', "
                                             "'packages/rust/src/c.rs:1']"))

    def test_slug_matches_github_anchors(self) -> None:
        self.assertEqual(audit.slug("Sign-off (Developer Certificate of Origin)"),
                         "sign-off-developer-certificate-of-origin")
