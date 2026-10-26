"""Reading a file safely: regular files only, bounded size, strict UTF-8 (same as read.rs/.ts).

The path is opened first (``O_NONBLOCK``, so a FIFO cannot hang the open) and the open handle is
inspected, so there is no stat-then-open race. Size is enforced by reading at most one byte past
the limit, not by trusting the reported size.

Implements: C-010, C-011, C-012, C-013, C-080, C-081
"""

from __future__ import annotations

import os
import stat

from urim.limits import MAX_BYTES
from urim.problem import CANNOT_READ, NOT_REGULAR_FILE, NOT_UTF8, TOO_LARGE, Failure

_FLAGS = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)


def read_text(path: str) -> str:
    """Return the UTF-8 text of the regular file at ``path``; raises ``Failure`` otherwise."""
    try:
        fd = os.open(path, _FLAGS)
    except (OSError, ValueError):  # ValueError: embedded NUL in the path (bug B-3)
        raise Failure(CANNOT_READ) from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Failure(NOT_REGULAR_FILE)
        chunks: list[bytes] = []
        size = 0
        try:
            while size <= MAX_BYTES and (chunk := os.read(fd, MAX_BYTES + 1 - size)):
                chunks.append(chunk)
                size += len(chunk)
        except OSError:
            raise Failure(CANNOT_READ) from None
    finally:
        os.close(fd)
    if size > MAX_BYTES:
        raise Failure(TOO_LARGE)
    try:
        return b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError:
        raise Failure(NOT_UTF8) from None
