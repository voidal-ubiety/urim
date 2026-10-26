#!/usr/bin/env python3
"""Fail if any ID in CONTRACT.md lacks a test in any language, or a fixture uses an unknown ID.

An ID counts as tested in a language when the ID (``C-012`` or ``c012``) appears in that
language's test sources, or when it tags a case in a shared JSON file that the language
runs through a generic per-ID test (see the "Test mapping" section of CONTRACT.md).

An entry that applies to only some ports says so with a line such as
``- **Languages:** rust``; it must then be tested in exactly those languages.
IDs referenced by tests or fixtures but not declared in CONTRACT.md also fail.

A retired or resolved entry keeps its section with a ``- **Status:**`` line so the ID is never
reused. It needs no tests, and no test source or fixture may use it any more.

Every ``**Fixtures (n):**`` list must equal, in order, the sorted ``cases.json`` paths for that
ID, with ``n`` its length. An ID with ``cases.json`` cases must have such a list.
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


def fixture_problems(sections: dict[str, str]) -> list[str]:
    """Each ``Fixtures (n):`` list must match cases.json for its ID exactly."""
    paths: dict[str, list[str]] = {}
    for case in json.loads((ROOT / "fixtures" / "cases.json").read_text(encoding="utf-8"))["cases"]:
        paths.setdefault(case["id"], []).append(case["path"])
    problems: list[str] = []
    for id_, section in sections.items():
        want = sorted(paths.get(id_, []))
        listed = re.search(r"^- \*\*Fixtures \((\d+)\):\*\* (.+)$", section, re.M)
        if listed is None:
            if want:
                problems.append(f"{id_}: has {len(want)} cases.json case(s) but no Fixtures (n) list")
            continue
        got = re.findall(r"`([^`]+)`", listed.group(2))
        if got != want:
            problems.append(f"{id_}: Fixtures list {got} != cases.json {want}")
        elif int(listed.group(1)) != len(got):
            problems.append(f"{id_}: Fixtures ({listed.group(1)}) but {len(got)} listed")
    return problems


def main() -> int:
    contract = (ROOT / "CONTRACT.md").read_text(encoding="utf-8")
    parts = re.split(r"^(?=### [CD]-\d{3}\b)", contract, flags=re.M)
    sections = {m.group(1): s for s in parts if (m := re.match(r"### ([CD]-\d{3})\b", s))}
    required: dict[str, set[str]] = {}
    retired: set[str] = set()
    for id_, section in sections.items():
        if re.search(r"^- \*\*Status:\*\* ", section, re.M):
            retired.add(id_)
            continue
        langs = re.search(r"^- \*\*Languages:\*\* (.+)$", section, re.M)
        names = set(re.findall(r"js|python|rust", langs.group(1).lower())) if langs else set(LANGUAGES)
        required[id_] = names
    declared = set(sections)
    problems: list[str] = fixture_problems(sections)
    used = set().union(*(json_ids(n) for n in ("cases.json", "cli.json", "divergences.json")))
    problems += [f"{i}: used in fixtures but not declared in CONTRACT.md" for i in sorted(used - declared)]
    problems += [f"{i}: retired/resolved but still used in fixtures" for i in sorted(used & retired)]
    for lang, (globs, shared) in LANGUAGES.items():
        in_sources = {i for i in source_ids(globs) if not i.endswith("-000")}  # x000 = meta tests
        problems += [f"{i}: referenced in {lang} tests but not declared" for i in sorted(in_sources - declared)]
        problems += [f"{i}: retired/resolved but referenced in {lang} tests" for i in sorted(in_sources & retired)]
        tested = in_sources.union(*(json_ids(n) for n in shared))
        need = {i for i, langs in required.items() if lang in langs}
        problems += [f"{i}: no {lang} test" for i in sorted(need - tested)]
    for p in problems:
        print(f"contract-check: {p}", file=sys.stderr)
    if problems:
        return 1
    partial = sorted(i for i, langs in required.items() if langs != set(LANGUAGES))
    note = f" ({', '.join(partial)} port-specific)" if partial else ""
    print(
        f"contract-check OK: {len(required)} live IDs, each tested in every port it applies to{note};"
        f" {len(retired)} retired/resolved; fixture lists match cases.json"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
