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


class StubbedMain(unittest.TestCase):
    """main() with every rule stubbed out, in a temp ROOT; subclasses add the tests."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "packages/rust").mkdir(parents=True)
        shutil.copy(ROOT / "packages/rust/deny.toml", self.tmp / "packages/rust/deny.toml")
        self.saved = {n: getattr(audit, n) for n in
                      ("ROOT", "l1", "l2", "l4", "l5_py", "m1", "m3", "m5", "c1", "c3", "c4", "t1", "t4", "t5", "policy", "NOT_IMPLEMENTED")}
        self.saved_which = audit.shutil.which
        self.saved_l5_rust = audit.l5_rust
        self.addCleanup(self.restore)
        self.pol = audit.policy()
        audit.ROOT = self.tmp
        for n in ("l1", "l2", "l4", "m1", "m3", "m5", "c1", "c3", "c4", "t1", "t4", "t5"):
            setattr(audit, n, lambda *a: None)
        audit.l5_py = lambda *a: audit._missing("L5-Py", "uv")
        audit.policy = lambda: self.pol
        audit.shutil.which = lambda tool: None if tool == "cargo-deny" else "/bin/" + tool
        audit.NOT_IMPLEMENTED = ()  # once every rule is built, a missing tool alone exits 2
        audit.results.clear()
        audit.missing_tools.clear()
        audit.tool_missing = False

    def restore(self) -> None:
        for n, v in self.saved.items():
            setattr(audit, n, v)
        audit.shutil.which = self.saved_which
        audit.results.clear()
        getattr(audit, "missing_tools", {}).clear()
        getattr(audit, "broken_env", {}).clear()
        audit.subprocess = subprocess
        audit.tool_missing = False
        shutil.rmtree(self.tmp)

    def run_main(self, *argv: str) -> tuple[int, str]:
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = audit.main(list(argv or ["--release"]))
        return code, out.getvalue()


class MissingToolTest(StubbedMain):
    """--release names each missing tool and how to install it; exit 2 only when nothing FAILs."""

    def test_exit_2_names_every_missing_tool_and_its_install_command(self) -> None:
        code, out = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("cargo-deny (needed by L5-Rust; install: cargo install --locked cargo-deny)", out)
        self.assertIn("uv (needed by L5-Py; install: https://docs.astral.sh/uv/", out)

    def test_a_fail_still_exits_1_but_the_missing_tools_are_named(self) -> None:
        audit.m3 = lambda: audit.add("M3", "FAIL", "history")
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("a required tool is missing: cargo-deny", out)


class NotImplementedRuleTest(StubbedMain):
    """--release FAILs every unimplemented rule; a normal run SKIPs it; built rules are untouched."""

    def setUp(self) -> None:
        super().setUp()
        audit.shutil.which = lambda tool: "/bin/" + tool
        audit.l5_rust = lambda pol: audit.add("L5-Rust", "PASS", "stub")
        audit.l5_py = lambda *a: audit.add("L5-Py", "PASS", "stub")
        audit.m1 = lambda: audit.add("M1", "PASS", "stub")
        audit.NOT_IMPLEMENTED = ("L3", "T2")

    def restore(self) -> None:
        super().restore()
        audit.l5_rust = self.saved_l5_rust

    def statuses(self) -> dict[str, tuple[str, str]]:
        return {r["rule"]: (r["status"], r["detail"]) for r in audit.results}

    def test_release_fails_on_an_unimplemented_rule(self) -> None:
        code, out = self.run_main("--release")
        self.assertEqual(code, 1)
        s = self.statuses()
        for rule in ("L3", "T2"):
            self.assertEqual(s[rule], ("FAIL", f"{rule} not implemented; release mode requires every rule to be built"))
        self.assertIn("L3 not implemented; release mode requires every rule to be built", out)

    def test_a_normal_run_still_passes_with_skip(self) -> None:
        code, out = self.run_main("--offline")
        self.assertEqual(code, 0)
        s = self.statuses()
        self.assertEqual(s["L3"], ("SKIP", "not implemented yet"))
        self.assertEqual(s["T2"], ("SKIP", "not implemented yet"))
        self.assertIn("audit-legal: PASS", out)

    def test_implemented_rules_are_unaffected_by_release(self) -> None:
        self.run_main("--release")
        s = self.statuses()
        for rule in ("L5-Rust", "L5-Py", "M1"):
            self.assertEqual(s[rule], ("PASS", "stub"))
        self.assertEqual({r for r, (st, _) in s.items() if st == "FAIL"}, {"L3", "T2"})

    def test_only_listed_rules_are_turned_into_fail(self) -> None:
        # A SKIP from a built rule is not rewritten by the NOT_IMPLEMENTED step (L5-Py's own
        # release handling is covered by ReleaseL5PyTest).
        audit.m1 = lambda: audit.add("M1", "SKIP", "stub skip")
        audit.NOT_IMPLEMENTED = ()
        code, _ = self.run_main("--release")
        self.assertEqual(code, 0)
        self.assertEqual(self.statuses()["M1"], ("SKIP", "stub skip"))

    def test_the_real_list_matches_the_rules_not_built(self) -> None:
        self.assertEqual(self.saved["NOT_IMPLEMENTED"],
                         ("L3", "L5-JS", "L6", "L7", "L8", "T2", "T3", "C2", "M2", "M4"))


class ReleaseL5PyTest(StubbedMain):
    """--release never lets L5-Py SKIP and pass: --offline FAILs, a broken env exits 2 (spec, Exit codes)."""

    def setUp(self) -> None:
        super().setUp()
        (self.tmp / "packages/python").mkdir(parents=True)
        shutil.copy(ROOT / "packages/python/uv.lock", self.tmp / "packages/python/uv.lock")
        audit.l5_py = self.saved["l5_py"]
        audit.l5_rust = lambda pol: audit.add("L5-Rust", "PASS", "stub")
        audit.shutil.which = lambda tool: "/bin/" + tool

    def restore(self) -> None:
        super().restore()
        audit.l5_rust = self.saved_l5_rust

    def no_pypi(self) -> None:
        import types
        def run(cmd, **kw):  # noqa: ANN001, ANN003, ANN202 - stand-in for subprocess.run
            return subprocess.CompletedProcess(cmd, 2, "", "error: Failed to fetch: https://pypi.org/simple/pyyaml/")
        audit.subprocess = types.SimpleNamespace(run=run)

    def l5(self) -> tuple[str, str]:
        r = next(r for r in audit.results if r["rule"] == "L5-Py")
        return r["status"], r["detail"]

    def test_release_offline_fails_l5_py(self) -> None:
        code, out = self.run_main("--release", "--offline")
        self.assertEqual(code, 1)
        status, detail = self.l5()
        self.assertEqual(status, "FAIL")
        self.assertIn("--offline is not allowed with --release: release requires L5-Py to run", detail)

    def test_release_without_pypi_is_a_broken_environment_exit_2(self) -> None:
        self.no_pypi()
        code, out = self.run_main("--release")
        self.assertEqual(code, 2)
        status, detail = self.l5()
        self.assertEqual(status, "SKIP")
        self.assertIn("[--release] broken environment: could not build the runtime env", detail)
        self.assertIn("audit-legal: exit 2: the environment is broken", out)

    def test_release_broken_env_with_a_fail_exits_1_and_names_it(self) -> None:
        self.no_pypi()
        audit.m3 = lambda: audit.add("M3", "FAIL", "history")
        code, out = self.run_main("--release")
        self.assertEqual(code, 1)
        self.assertIn("audit-legal: FAIL (and the environment is broken; see above)", out)

    def test_normal_run_offline_still_skips_and_passes(self) -> None:
        code, out = self.run_main("--offline")
        self.assertEqual(code, 0)
        self.assertEqual(self.l5(), ("SKIP", "--offline: installing the locked runtime deps needs PyPI"))

    def test_normal_run_without_pypi_still_skips_and_passes(self) -> None:
        self.no_pypi()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(out):
            code = audit.main([])
        self.assertEqual(code, 0)
        status, detail = self.l5()
        self.assertEqual(status, "SKIP")
        self.assertTrue(detail.startswith("could not build the runtime env: error: Failed to fetch"), detail)
        self.assertNotIn("broken environment", out.getvalue())
