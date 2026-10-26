"""`urim check`: validate a hoshen lockfile or a contract's top-level shape.

Behavior is specified in fixtures/README.md and shared with the JS and Rust ports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

SUPPORTED_HOSHEN = frozenset({1})
CONTRACT_REQUIRED = ("contract", "version", "state", "questions")
NOT_URIM = "not a urim document: expected a lockfile with 'hoshen' or a contract with 'dctp' or 'urim'"


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    line: str

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1


class _InvalidYaml(Exception):
    pass


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


def _construct_int(loader: yaml.SafeLoader, node: yaml.Node) -> int:
    value = loader.construct_scalar(node)
    if value.startswith("0o"):
        number = int(value[2:], 8)
    elif value.startswith("0x"):
        number = int(value[2:], 16)
    else:
        number = int(value, 10)
    if not _INT_MIN <= number <= _INT_MAX:
        raise _InvalidYaml("integer out of 64-bit range")
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
            raise _InvalidYaml("mapping keys must be scalars")
        key = loader.construct_object(key_node, deep=True)
        if (type(key), key) in seen:
            raise _InvalidYaml("duplicate key")
        seen.add((type(key), key))
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_CoreLoader.add_constructor("tag:yaml.org,2002:int", _construct_int)
_CoreLoader.add_constructor("tag:yaml.org,2002:map", _construct_mapping)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _fail(file: str, problem: str) -> CheckResult:
    return CheckResult(False, f"{file}: error: {problem}")


def check_text(file: str, text: str) -> CheckResult:
    text = text.removeprefix("\ufeff")
    try:
        root = yaml.load(text, Loader=_CoreLoader)  # noqa: S506 - restricted safe loader
    except (yaml.YAMLError, _InvalidYaml, ValueError, TypeError):
        return _fail(file, "invalid YAML")

    if not isinstance(root, dict):
        return _fail(file, "root must be a mapping")

    if "hoshen" in root:
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
        return CheckResult(True, f"{file}: ok (lockfile, hoshen {hoshen}, urim {root['urim']})")

    if "dctp" in root or "urim" in root:
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
        return CheckResult(
            True, f"{file}: ok (contract {root['contract']}@{root['version']}, {key} {root[key]})"
        )

    return _fail(file, NOT_URIM)


def check_file(path: str) -> CheckResult:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return _fail(path, "cannot read file")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(path, "file is not valid UTF-8")
    return check_text(path, text)
