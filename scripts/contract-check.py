#!/usr/bin/env python3
"""Fail if any ID in CONTRACT.md lacks a test in any language, or a fixture uses an unknown ID.

An ID counts as tested in a language when the ID (``C-012`` or ``c012``) appears in that
language's test sources, or when it tags a case in a shared JSON file that the language
runs through a generic per-ID test (see the "Test mapping" section of CONTRACT.md).

An entry that applies to only some ports says so with a line such as
``- **Languages:** rust``; it must then be tested in exactly those languages.
IDs referenced by tests or fixtures but not declared in CONTRACT.md also fail.
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
    sections = re.split(r"^(?=### [CD]-\d{3}\b)", contract, flags=re.M)
    required: dict[str, set[str]] = {}
    for section in sections:
        head = re.match(r"### ([CD]-\d{3})\b", section)
        if head:
            langs = re.search(r"^- \*\*Languages:\*\* (.+)$", section, re.M)
            names = set(re.findall(r"js|python|rust", langs.group(1).lower())) if langs else set(LANGUAGES)
            required[head.group(1)] = names
    declared = set(required)
    problems: list[str] = []
    used = set().union(*(json_ids(n) for n in ("cases.json", "cli.json", "divergences.json")))
    problems += [f"{i}: used in fixtures but not declared in CONTRACT.md" for i in sorted(used - declared)]
    for lang, (globs, shared) in LANGUAGES.items():
        in_sources = {i for i in source_ids(globs) if not i.endswith("-000")}  # x000 = meta tests
        problems += [f"{i}: referenced in {lang} tests but not declared" for i in sorted(in_sources - declared)]
        tested = in_sources.union(*(json_ids(n) for n in shared))
        need = {i for i, langs in required.items() if lang in langs}
        problems += [f"{i}: no {lang} test" for i in sorted(need - tested)]
    for p in problems:
        print(f"contract-check: {p}", file=sys.stderr)
    if problems:
        return 1
    partial = sorted(i for i, langs in required.items() if langs != set(LANGUAGES))
    note = f" ({', '.join(partial)} port-specific)" if partial else ""
    print(f"contract-check OK: {len(declared)} IDs, each tested in every port it applies to{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
