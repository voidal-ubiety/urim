#!/usr/bin/env python3
"""Hostile-input suite: run all three `urim check` CLIs on hostile inputs, under bounds.

Inputs:
  - every cases.json case whose path is under fixtures/hostile/ (static files, also run by
    each port's own tests and by parity.sh);
  - every case in fixtures/hostile.json (generated large inputs and special files: FIFO,
    /dev/zero, symlinks, a path containing ANSI and bidi characters).

For each implementation and case it requires the expected exit code and output, a wall time
under max_ms (the process is killed at 2 x max_ms, so a hang fails instead of blocking), and
a peak RSS under max_rss_mib. RSS comes from scripts/rss-exec.c (compiled with cc into a temp
directory), because a plain wait4 ru_maxrss includes the RSS of the forking harness itself
(Linux carries the pre-exec peak across exec); without a C compiler it falls back to wait4
and says so, and the reported RSS then has a floor of the harness's own RSS. It also requires that the canary file
named in hostile.json, which the deserialization-gadget fixtures try to create, never exists.

Usage: scripts/hostile.py [--only js,python,rust] [--case SUBSTRING] [--report]
Env:   PYTHON (interpreter with urim installed; default packages/python/.venv/bin/python),
       URIM_RUST (default packages/rust/target/debug/urim).
Exit:  0 all passed; 1 a case failed; 2 setup error.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import select
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "fixtures"


def commands() -> dict[str, list[str]]:
    py = os.environ.get("PYTHON") or str(ROOT / "packages/python/.venv/bin/python")
    rs = os.environ.get("URIM_RUST") or str(ROOT / "packages/rust/target/debug/urim")
    return {
        "js": ["node", str(ROOT / "packages/js/dist/cli.js")],
        "python": [py, "-m", "urim"],
        "rust": [rs],
    }


def escape(path: str) -> str:
    """C-089 escaping, for the characters this suite puts in paths."""
    return "".join(f"\\u{{{ord(ch):04X}}}" if ch in "\x1b\x07\u202e" else ch for ch in path)


def build(case: dict, tmp: Path) -> str:
    """Create the input for a hostile.json case and return the path to pass."""
    name = case["name"]
    special = case.get("special")
    if special:
        fifo = tmp / "fifo"
        if not fifo.exists():
            os.mkfifo(fifo)
        target = {
            "fifo": str(fifo),
            "dev-zero": "/dev/zero",
            "dev-urandom": "/dev/urandom",
            "directory": str(tmp),
        }
        if special in target:
            return target[special]
        link = tmp / name
        if not link.is_symlink():
            if special == "symlink-dev-zero":
                link.symlink_to("/dev/zero")
            elif special == "symlink-fifo":
                link.symlink_to(fifo)
            elif special == "dangling-symlink":
                link.symlink_to(tmp / "does-not-exist")
            elif special == "symlink-loop":
                link.symlink_to(link)
        if special == "ansi-path":
            path = tmp / "a\x1b[31mred\x1b]0;title\x07\u202eb.lock"
            path.write_text("[]\n")
            return str(path)
        return str(link)
    text = "".join(piece * n for piece, n in case.get("pieces", []))
    gen = case.get("generate")
    count = case.get("count", 0)
    if gen == "many-keys":
        text += "hoshen: 1\nurim: x\n" + "".join(f"k{i}: {i}\n" for i in range(count))
    elif gen == "block-nest":
        text += "".join("  " * (i + 1) + "a:\n" for i in range(count))
    elif gen == "invisible-keys":
        text += "hoshen: 1\nurim: x\n" + "".join(f"k{i}\u200b: 1\n" for i in range(count))
    text += case.get("suffix", "")
    data = text.encode("utf-8")
    if "bytes_suffix_hex" in case:
        data += bytes.fromhex(case["bytes_suffix_hex"]) * case["bytes_suffix_repeat"]
    path = tmp / f"{name}.yaml"
    path.write_bytes(data)
    return str(path)


def rss_helper(tmp: Path) -> str | None:
    """Compile scripts/rss-exec.c; None (fall back to wait4) if no C compiler works."""
    out = tmp / "rss-exec"
    for cc in ("cc", "gcc", "clang"):
        try:
            done = subprocess.run([cc, "-O2", "-o", str(out), str(ROOT / "scripts/rss-exec.c")],
                                  capture_output=True)
        except FileNotFoundError:
            continue
        if done.returncode == 0:
            return str(out)
    return None


def run(cmd: list[str], path: str, cwd: Path, max_ms: int,
        helper: str | None) -> tuple[int | None, str, float, float]:
    """Run `cmd check path`; return (exit or None if killed, output, ms, peak RSS MiB)."""
    start = time.monotonic()
    rfd, wfd = os.pipe() if helper else (-1, -1)
    proc = subprocess.Popen(
        [helper, str(wfd), *cmd, "check", path] if helper else [*cmd, "check", path],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        pass_fds=(wfd,) if helper else (),
    )
    if helper:
        os.close(wfd)
    assert proc.stdout is not None
    chunks: list[bytes] = []
    deadline = start + 2 * max_ms / 1000
    fd = proc.stdout.fileno()
    killed = False
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            proc.send_signal(signal.SIGKILL)
            killed = True
            left = 5
        ready, _, _ = select.select([fd], [], [], left)
        if ready:
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
        elif killed:
            break
    _, status, usage = os.wait4(proc.pid, 0)
    proc.returncode = 0
    ms = (time.monotonic() - start) * 1000
    code = None if killed else os.waitstatus_to_exitcode(status)
    rss = usage.ru_maxrss / 1024  # Linux reports KiB
    if helper:
        reported = os.read(rfd, 64).decode().strip()
        os.close(rfd)
        if reported:
            rss = int(reported) / 1024
    return code, b"".join(chunks).decode("utf-8", "replace").rstrip("\n"), ms, rss


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="js,python,rust")
    ap.add_argument("--case", default="", help="run only cases whose name contains this")
    ap.add_argument("--report", action="store_true", help="print time and RSS for every run")
    args = ap.parse_args()
    manifest = json.loads((FIX / "hostile.json").read_text())
    bounds = manifest["bounds"]
    canary = Path(manifest["canary"])
    cmds = {k: v for k, v in commands().items() if k in args.only.split(",")}
    for impl, cmd in cmds.items():
        if not Path(cmd[0] if impl != "js" else cmd[1]).exists() and impl != "js":
            print(f"hostile: {impl} executable not found: {cmd[0]}", file=sys.stderr)
            return 2
    if canary.exists():
        canary.unlink()

    cases = []
    for c in json.loads((FIX / "cases.json").read_text())["cases"]:
        if c["path"].startswith("hostile/"):
            cases.append({"id": c["id"], "name": c["path"], "path": "fixtures/" + c["path"],
                          "exit": c["exit"], "output": c["output"]})
    fails = 0
    worst: dict[str, tuple[float, float]] = {k: (0.0, 0.0) for k in cmds}
    with tempfile.TemporaryDirectory(prefix="urim-hostile-") as tmpdir:
        tmp = Path(tmpdir)
        helper = rss_helper(tmp)
        if helper is None:
            print("hostile: no C compiler; RSS from wait4 includes the harness's own RSS",
                  file=sys.stderr)
        for c in manifest["cases"]:
            entry = dict(c)
            entry["path"] = build(c, tmp)
            if "output_pieces" in c:
                entry["output"] = "".join(p * n for p, n in c["output_pieces"])
            cases.append(entry)
        cases = [c for c in cases if args.case in c["name"]]
        for c in cases:
            want = c["output"].replace("{escaped_file}", escape(c["path"])).replace("{file}", c["path"])
            for impl, cmd in cmds.items():
                lim = {**bounds[impl], **c.get("bounds", {}).get(impl, {})}
                code, out, ms, rss = run(cmd, c["path"], ROOT, lim["max_ms"], helper)
                worst[impl] = (max(worst[impl][0], ms), max(worst[impl][1], rss))
                problems = []
                if code is None:
                    problems.append(f"killed after {ms:.0f} ms (hang?)")
                elif code != c["exit"]:
                    problems.append(f"exit {code}, want {c['exit']}")
                if code is not None and out != want:
                    problems.append(f"output {out[:200]!r}, want {want[:200]!r}")
                if ms > lim["max_ms"]:
                    problems.append(f"{ms:.0f} ms > {lim['max_ms']} ms")
                if rss > lim["max_rss_mib"]:
                    problems.append(f"{rss:.1f} MiB > {lim['max_rss_mib']} MiB")
                if canary.exists():
                    problems.append(f"canary {canary} was created")
                    canary.unlink()
                if args.report:
                    print(f"  {impl:6} {ms:7.0f} ms {rss:6.1f} MiB  {c['id']} {c['name']}")
                if problems:
                    fails += 1
                    print(f"FAIL [{impl}] {c['id']} {c['name']}: " + "; ".join(problems))
    summary = ", ".join(f"{k} max {t:.0f} ms / {r:.1f} MiB" for k, (t, r) in worst.items())
    if fails:
        print(f"hostile: {fails} failure(s) over {len(cases)} cases ({summary})")
        return 1
    print(f"hostile OK: {len(cases)} cases x {len(cmds)} implementations within bounds, "
          f"no canary ({summary})")
    return 0


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    sys.exit(main())
