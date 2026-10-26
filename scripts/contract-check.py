#!/usr/bin/env python3
"""Fail if any ID in CONTRACT.md lacks a test in any language, or a fixture uses an unknown ID.

An ID counts as tested in a language when the ID (``C-012`` or ``c012``) appears in that
language's test sources, or when it tags a case in a shared JSON file that the language
runs through a generic per-ID test (see the "Test mapping" section of CONTRACT.md).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ID = re.compile(r"\b([CD])-(\d{3})\b")

# language -> (test source globs, shared JSON files consumed generically)
LANGUAGES = {
    "js": (["packages/js/test/*.mjs"], ["cases.json", "cli.json", "divergences.json"]),
    "python": (["packages/python/tests/*.py"], ["cases.json", "cli.json", "divergences.json"]),
    "rust": (["packages/rust/tests/*.rs", "packages/rust/tests/**/*.rs"], ["divergences.json"]),
}


def json_ids(name: str) -> set[str]:
    cases = json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))["cases"]
    return {c["id"] for c in cases}


def source_ids(globs: list[str]) -> set[str]:
    found: set[str] = set()
    for pattern in globs:
        for path in ROOT.glob(pattern):
            text = path.read_text(encoding="utf-8")
            found |= {f"{k}-{n}" for k, n in ID.findall(text)}
            found |= {f"{k.upper()}-{n}" for k, n in re.findall(r"(?<![A-Za-z0-9])([cd])(\d{3})_", text)}
    return found


def main() -> int:
    contract = (ROOT / "CONTRACT.md").read_text(encoding="utf-8")
    declared = {f"{k}-{n}" for k, n in re.findall(r"^### ([CD])-(\d{3})\b", contract, re.M)}
    problems: list[str] = []
    used = set().union(*(json_ids(n) for n in ("cases.json", "cli.json", "divergences.json")))
    problems += [f"{i}: used in fixtures but not declared in CONTRACT.md" for i in sorted(used - declared)]
    for lang, (globs, shared) in LANGUAGES.items():
        tested = source_ids(globs).union(*(json_ids(n) for n in shared))
        problems += [f"{i}: no {lang} test" for i in sorted(declared - tested)]
    for p in problems:
        print(f"contract-check: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"contract-check OK: {len(declared)} IDs, each tested in js, python and rust")
    return 0


if __name__ == "__main__":
    sys.exit(main())
