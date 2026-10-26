"""Cross-field rules, run after the closed schema has passed (CONTRACT.md C-097, C-099).

Same order as rules.ts/rules.rs. The schema has already fixed every shape, so the accessors below
only distinguish "present" from "absent" (an absent optional key reads as None).

Implements: C-097, C-099
"""

from __future__ import annotations

import re

from urim.display import sanitize
from urim.problem import (
    Failure,
    also_preferred,
    no_emulation,
    not_a_target,
    not_an_answer,
    undeclared_experimental,
    unknown_question,
)
from urim.schema import Path, path_text
from urim.schema_gen import EMULATIONS, EXPERIMENTAL_QUESTION_TYPES

_CANONICAL_INDEX = re.compile(r"0|[1-9][0-9]*")


def _get(v: object, key: object) -> object:
    """``v[key]`` of a mapping or a list; None when absent."""
    if isinstance(v, dict):
        return v.get(str(key))
    if isinstance(v, list):
        i = int(str(key))
        return v[i] if i < len(v) else None
    return None


def _entries(v: object) -> list[tuple[str | int, object]]:
    """Return the entries of a mapping (by key) or a list (by index); none when absent."""
    if isinstance(v, dict):
        return [(str(k), x) for k, x in v.items()]
    if isinstance(v, list):
        return list(enumerate(v))
    return []


def _is_answer(question: object, answer: str) -> bool:
    """Whether ``answer`` answers ``question`` (SPEC §5.4): an option key, yes/no, or a level index."""
    kind = _get(question, "type")
    if kind == "choice":
        return _get(_get(question, "options"), answer) is not None
    if kind == "yesno":
        return answer in ("yes", "no")
    if kind == "score":
        return (
            _CANONICAL_INDEX.fullmatch(answer) is not None
            and _get(_get(question, "levels"), answer) is not None
        )
    return False


def _extension_fallback(path: Path, ext: object) -> None:
    """Check an extension's ``fallback: {emulate: name}``: 0.2 registers no extension emulations."""
    name = _get(_get(ext, "fallback"), "emulate")
    if isinstance(name, str):
        raise Failure(no_emulation(path_text((*path, "fallback", "emulate")), sanitize(name)))


def _question_types(root: dict[str, object]) -> None:
    for name, question in _entries(root.get("questions")):
        kind = _get(question, "type")
        declaration = f"question_types.{kind}"
        if (
            kind in EXPERIMENTAL_QUESTION_TYPES
            and _get(root.get("requires"), declaration) is None
            and _get(root.get("prefers"), declaration) is None
        ):
            raise Failure(undeclared_experimental(path_text(("questions", name, "type")), str(kind)))


def _policy(root: dict[str, object]) -> None:
    for rule_id, rule in _entries(root.get("policy")):
        asked = _get(rule, "question")
        question = _get(root.get("questions"), asked)
        if question is None:
            raise Failure(unknown_question(path_text(("policy", rule_id, "question")), sanitize(str(asked))))
        answer = _get(_get(rule, "when"), "answer")
        if isinstance(answer, str) and not _is_answer(question, answer):
            raise Failure(
                not_an_answer(path_text(("policy", rule_id, "when", "answer")), sanitize(str(asked)))
            )
    for name, _ in _entries(_get(root.get("eval"), "paraphrases")):
        if _get(root.get("questions"), name) is None:
            raise Failure(unknown_question(path_text(("eval", "paraphrases", name)), sanitize(str(name))))


def _capabilities(root: dict[str, object]) -> None:
    prefers = root.get("prefers")
    for cap, _ in _entries(root.get("requires")):
        if _get(prefers, cap) is not None:
            raise Failure(also_preferred(path_text(("requires", cap))))
    for cap, preference in _entries(prefers):
        emulation = _get(_get(preference, "fallback"), "emulate")
        if isinstance(emulation, str) and emulation not in EMULATIONS.get(str(cap), ()):
            raise Failure(
                no_emulation(path_text(("prefers", cap, "fallback", "emulate")), sanitize(emulation))
            )
    for key, ext in _entries(root):
        if str(key).startswith("x-"):
            _extension_fallback((key,), ext)
    for name, question in _entries(root.get("questions")):
        for key, ext in _entries(question):
            if str(key).startswith("x-"):
                _extension_fallback(("questions", name, key), ext)


def contract_rules(root: dict[str, object]) -> None:
    """Apply the contract rules, in this order: question types, policy, eval, requires/prefers, emulations."""
    _question_types(root)
    _policy(root)
    _capabilities(root)


def lockfile_rules(root: dict[str, object]) -> None:
    """Apply the lockfile rules: each ``active`` and ``standby`` target is a key of ``targets``."""
    for contract_id, entry in _entries(_get(root, "contracts")):
        targets = _get(entry, "targets")
        where = path_text(("contracts", contract_id, "targets"))
        active = _get(entry, "active")
        if _get(targets, active) is None:
            raise Failure(
                not_a_target(path_text(("contracts", contract_id, "active")), sanitize(str(active)), where)
            )
        for i, target in _entries(_get(entry, "standby")):
            if _get(targets, target) is None:
                raise Failure(
                    not_a_target(
                        path_text(("contracts", contract_id, "standby", i)), sanitize(str(target)), where
                    )
                )
