# SPDX-License-Identifier: Apache-2.0
"""The sandbox tripwire flags each forbidden syscall and allows threads and read-only opens."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "check-sandbox"
_loader = importlib.machinery.SourceFileLoader("check_sandbox", str(PATH))
_spec = importlib.util.spec_from_loader("check_sandbox", _loader)
assert _spec is not None
sandbox = importlib.util.module_from_spec(_spec)
_loader.exec_module(sandbox)

OK = """\
100 execve("/usr/bin/node", ["node"], 0x0 /* 1 vars */) = 0
100 openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3
100 clone3({flags=CLONE_VM|CLONE_FS|CLONE_FILES|CLONE_SIGHAND|CLONE_THREAD|CLONE_SYSVSEM, ...}, 88) = 101
"""


class Violations(unittest.TestCase):
    def test_clean_trace_passes(self) -> None:
        self.assertEqual(sandbox.violations(OK), [])

    def test_each_forbidden_call_is_flagged(self) -> None:
        for line in (
            '100 socket(AF_INET, SOCK_STREAM, 0) = 3',
            '100 connect(3, {sa_family=AF_INET}, 16) = 0',
            '100 execve("/bin/sh", ["sh"], 0x0) = 0',
            '100 clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID|SIGCHLD) = 102',
            '100 vfork() = 103',
            '100 openat(AT_FDCWD, "/tmp/pwned", O_WRONLY|O_CREAT|O_TRUNC, 0666) = 3',
            '100 openat(AT_FDCWD, "x", O_RDWR) = 3',
            '100 creat("x", 0644) = 3',
        ):
            with self.subTest(line=line):
                self.assertEqual(sandbox.violations(OK + line + "\n"), [line])


if __name__ == "__main__":
    unittest.main()
