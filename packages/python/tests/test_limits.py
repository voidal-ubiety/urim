"""C-080, C-081, C-089: limits and file-type rules that need generated files, not fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import urim
from tests.sealed import SEALED_LOCK
from urim.check import check_file, check_text

LOCK = SEALED_LOCK
TOO_LARGE = "error: file too large (max 1048576 bytes)"


def _padded(size: int) -> str:
    """A valid lockfile padded with a comment to exactly ``size`` bytes."""
    return f"{LOCK}#{'x' * (size - len(LOCK) - 2)}\n"


def test_c080_limits_are_exported() -> None:
    assert (urim.MAX_BYTES, urim.MAX_DEPTH) == (1_048_576, 64)


def test_c080_exactly_max_bytes_is_accepted_one_more_is_too_large(tmp_path: Path) -> None:
    ok = tmp_path / "max.lock"
    ok.write_text(_padded(urim.MAX_BYTES), encoding="utf-8")
    assert check_file(str(ok)).line == f"{ok}: ok (lockfile, hoshen 2, urim 0.2)"
    big = tmp_path / "big.lock"
    big.write_text(_padded(urim.MAX_BYTES + 1), encoding="utf-8")
    assert check_file(str(big)).line == f"{big}: {TOO_LARGE}"
    assert check_text("t", _padded(urim.MAX_BYTES + 1)).line == f"t: {TOO_LARGE}"
    # Bytes, not code points: 2-byte characters count twice.
    assert check_text("t", LOCK + "#" + "é" * (urim.MAX_BYTES // 2)).line == f"t: {TOO_LARGE}"


def test_c081_fifos_and_devices_are_refused_symlinks_followed(tmp_path: Path) -> None:
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    assert check_file(str(fifo)).line == f"{fifo}: error: not a regular file"
    assert check_file("/dev/zero").line == "/dev/zero: error: not a regular file"
    assert check_file("/dev/null").line == "/dev/null: error: not a regular file"
    target = tmp_path / "target.lock"
    target.write_text(LOCK, encoding="utf-8")
    link = tmp_path / "link.lock"
    link.symlink_to(target)
    assert check_file(str(link)).line == f"{link}: ok (lockfile, hoshen 2, urim 0.2)"


def test_c013_read_error_after_open_is_cannot_read() -> None:
    # /proc/self/mem opens as a regular file but reading offset 0 fails with EIO.
    assert check_file("/proc/self/mem").line == "/proc/self/mem: error: cannot read file"


def test_c013_nul_in_the_path_is_cannot_read() -> None:
    # Bug B-3: os.open raises ValueError (not OSError) for an embedded NUL, which escaped the API.
    result = check_file("a\x00b")
    assert (result.ok, result.exit_code) == (False, 1)
    assert result.line == "a\\u{0000}b: error: cannot read file"


def test_c089_unsafe_characters_in_the_file_name_are_escaped() -> None:
    line = check_text("a\x1b[31mb\u202e\x85", "[]").line
    assert line == "a\\u{001B}[31mb\\u{202E}\\u{0085}: error: root must be a mapping"
    assert check_text("\U000e0041", "[]").line == "\\u{E0041}: error: root must be a mapping"
    # Undecodable path bytes (surrogateescape) are shown as U+FFFD, as in the other ports.
    assert check_text(os.fsdecode(b"a\xffb"), "[]").line == "a\ufffdb: error: root must be a mapping"
