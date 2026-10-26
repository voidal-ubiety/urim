"""`urim check`: validate a hoshen lockfile or a contract's top-level shape.

Behavior is specified in CONTRACT.md (repo root) and shared with the JS and Rust ports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_HOSHEN = frozenset({1})
CONTRACT_REQUIRED = ("contract", "version", "state", "questions")
NOT_URIM = "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one check: ``line`` is the single line the CLI prints."""

    ok: bool
    line: str

    @property
    def exit_code(self) -> int:
        """Process exit code for this result: 0 when ok, 1 otherwise."""
        return 0 if self.ok else 1


class _InvalidYamlError(Exception):
    """Raised inside the loader for input the contract treats as invalid YAML."""


class _CoreLoader(yaml.SafeLoader):
    """SafeLoader restricted to YAML 1.2 core-schema scalars, rejecting duplicate keys."""


_CoreLoader.yaml_implicit_resolvers = {}
_CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:null", re.compile(r"^(?:~|null|Null|NULL|)$"), ["~", "n", "N", ""]
)
_CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)
_CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^(?:[-+]?(?:0|[1-9][0-9]*)|0o[0-7]+|0x[0-9a-fA-F]+)$"),
    list("-+0123456789"),
)
_CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
        r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
    ),
    list("-+.0123456789"),
)


_INT_MIN = -(2**63)
_INT_MAX = 2**64 - 1


def _construct_int(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> int:
    value = loader.construct_scalar(node)
    if value.startswith("0o"):
        number = int(value[2:], 8)
    elif value.startswith("0x"):
        number = int(value[2:], 16)
    else:
        number = int(value, 10)
    if not _INT_MIN <= number <= _INT_MAX:
        raise _InvalidYamlError("integer out of 64-bit range")
    return number


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    # Python treats True == 1 == 1.0 as the same dict key; YAML does not.
    # Compare keys by (type, value) so they only count as duplicates when the
    # YAML type matches. Only str keys are looked up afterwards, and a str never
    # collides with a bool/int/float, so overwriting below loses nothing used.
    seen: set[tuple[type, Any]] = set()
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode):
            raise _InvalidYamlError("mapping keys must be scalars")
        key = loader.construct_object(key_node, deep=True)
        if (type(key), key) in seen:
            raise _InvalidYamlError("duplicate key")
        seen.add((type(key), key))
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_CoreLoader.add_constructor("tag:yaml.org,2002:int", _construct_int)
_CoreLoader.add_constructor("tag:yaml.org,2002:map", _construct_mapping)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _fail(file: str, problem: str) -> CheckResult:
    return CheckResult(ok=False, line=f"{file}: error: {problem}")


def _pass(file: str, detail: str) -> CheckResult:
    return CheckResult(ok=True, line=f"{file}: ok ({detail})")


def check_text(file: str, text: str) -> CheckResult:
    """Check YAML ``text``; ``file`` is used only in the message."""
    text = text.removeprefix("\ufeff")
    try:
        root = yaml.load(text, Loader=_CoreLoader)  # noqa: S506 - restricted safe loader
    except (yaml.YAMLError, _InvalidYamlError, ValueError, TypeError):
        return _fail(file, "invalid YAML")

    if not isinstance(root, dict):
        return _fail(file, "root must be a mapping")

    if "hoshen" in root:
        return _check_lockfile(file, root)
    if "dctp" in root or "urim" in root:
        return _check_contract(file, root)
    return _fail(file, NOT_URIM)


def _check_lockfile(file: str, root: dict[Any, Any]) -> CheckResult:
    hoshen = root["hoshen"]
    if not _is_int(hoshen):
        return _fail(file, "hoshen must be an integer")
    if hoshen not in SUPPORTED_HOSHEN:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_HOSHEN))
        return _fail(file, f"unsupported hoshen version {hoshen} (supported: {supported})")
    if "urim" not in root:
        return _fail(file, "missing required key(s): urim")
    if not isinstance(root["urim"], str):
        return _fail(file, "urim must be a string")
    return _pass(file, f"lockfile, hoshen {hoshen}, urim {root['urim']}")


def _check_contract(file: str, root: dict[Any, Any]) -> CheckResult:
    if "dctp" in root and "urim" in root:
        return _fail(file, "set only one of 'dctp' or 'urim'")
    key = "dctp" if "dctp" in root else "urim"
    if not isinstance(root[key], str):
        return _fail(file, f"{key} must be a string")
    missing = [k for k in CONTRACT_REQUIRED if k not in root]
    if missing:
        return _fail(file, "missing required key(s): " + ", ".join(missing))
    for k in ("contract", "version"):
        if not isinstance(root[k], str):
            return _fail(file, f"{k} must be a string")
    if not isinstance(root["state"], dict):
        return _fail(file, "state must be a mapping")
    if not isinstance(root["questions"], dict) or not root["questions"]:
        return _fail(file, "questions must be a non-empty mapping")
    return _pass(file, f"contract {root['contract']}@{root['version']}, {key} {root[key]}")


def check_file(path: str) -> CheckResult:
    """Read and check the file at ``path``; the message names ``path`` exactly as given."""
    try:
        with Path(path).open("rb") as fh:
            data = fh.read()
    except OSError:
        return _fail(path, "cannot read file")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(path, "file is not valid UTF-8")
    return check_text(path, text)
