"""Command-line entry point: `urim check <file>`."""

from __future__ import annotations

import sys

from urim import __version__
from urim.check import check_file

USAGE = "usage: urim check <file>"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["--version"], ["-V"]):
        print(f"urim {__version__}")
        return 0
    if args in (["--help"], ["-h"]):
        print(USAGE)
        return 0
    if len(args) != 2 or args[0] != "check":
        print(USAGE, file=sys.stderr)
        return 2
    result = check_file(args[1])
    print(result.line, file=sys.stdout if result.ok else sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
