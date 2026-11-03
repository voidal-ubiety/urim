"""C: definition helpers. Each returns frozen data; invalid shapes raise invalid_definition at import time."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

from .descriptors import DESCRIPTORS
from .errors import FAILOVER_TYPES, Issue, invalid_definition
from .types import CONFIDENCE_RULE, Camp, Definition, Objective, Question, QuestionType, SchemaAdapter, Threshold, Tier

_EXACT_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-_]*$")


def tier(*, provider: str, model: str, version: str, camp: Camp, question_types: Sequence[QuestionType]) -> Tier:
    if not _EXACT_VERSION.match(version):
        raise invalid_definition([Issue("version", f'exact version required, got "{version}"')])
    return Tier(f"{provider}/{model}@{version}", provider, model, version, camp, tuple(question_types))


def _question(type: QuestionType, prompt: str, options: Mapping[str, str]) -> Question:
    if len(options) < 2:
        raise invalid_definition([Issue(prompt, f"{type} needs at least two options")])
    return Question(type, prompt, MappingProxyType(dict(options)))


def noul(prompt: str, *, yes: str, no: str) -> Question:
    return _question("noul", prompt, {"yes": yes, "no": no})


def choice(prompt: str, options: Mapping[str, str]) -> Question:
    return _question("choice", prompt, options)


def score(prompt: str, levels: Mapping[str, str]) -> Question:
    """Levels in ascending order; key order is the order."""
    return _question("score", prompt, levels)


def threshold(*, on: str, default: float | None = None, objective: Objective | None = None) -> Threshold:
    if default is not None and not (0 <= default <= 1):
        raise invalid_definition([Issue(on, f"default must be within 0..1, got {default}")])
    return Threshold(on, default, objective or Objective())


def _tier_issues(tiers: tuple[Tier, ...], questions: Mapping[str, Question]) -> list[Issue]:
    if not tiers:
        return [Issue("tiers", "at least one tier required")]
    ids = [t.id for t in tiers]
    dup = [Issue("tiers", f"duplicate tier {i}") for n, i in enumerate(ids) if ids.index(i) != n]
    unsupported = [
        Issue(f"questions.{name}", f"{t.id} cannot answer {q.type}")
        for t in tiers
        for name, q in questions.items()
        if q.type not in t.question_types
    ]
    wrong = [
        Issue("tiers", f"{t.id}: {t.provider} speaks the {DESCRIPTORS[t.provider].camp} body, not {t.camp}")
        for t in tiers
        if t.provider in DESCRIPTORS and DESCRIPTORS[t.provider].camp != t.camp
    ]
    return [*dup, *unsupported, *wrong]


def define_decision(
    *,
    contract: str,
    tiers: Sequence[Tier],
    input: SchemaAdapter,
    questions: Mapping[str, Question],
    failover_on: Sequence[str],
    thresholds: Mapping[str, Threshold] | None = None,
    prepare: Callable[[Any], Any] | None = None,
    interpret: Callable[..., Any] | None = None,
) -> Definition:
    th = dict(thresholds or {})
    issues = [
        *_tier_issues(tuple(tiers), questions),
        *[Issue(f"thresholds.{n}", f'unknown question "{t.on}"') for n, t in th.items() if t.on not in questions],
        *[Issue("failover.on", f'"{t}" can never fail over') for t in failover_on if t not in FAILOVER_TYPES],
    ]
    if issues:
        raise invalid_definition(issues)
    return Definition(
        contract,
        tuple(tiers),
        input,
        MappingProxyType(dict(questions)),
        tuple(failover_on),
        MappingProxyType(th),
        CONFIDENCE_RULE,
        prepare,
        interpret,
    )
