"""The closed-schema interpreter: checks a value against a generated schema node (schema_gen.py).

Same algorithm as schema.ts/schema.rs; CONTRACT.md C-095 states the order.

Implements: C-095, C-096, C-097, C-088, C-092
"""

from __future__ import annotations

import math
import re

from urim.display import has_invisible, sanitize
from urim.formats import matches
from urim.node import Alt, Bool, Enum, Field, Fmt, Int, Leaf, List, Map, Node, Num, Obj, One, Opaque, Str
from urim.problem import (
    Failure,
    bad_key,
    invisible_in,
    missing_keys_in,
    must_be,
    non_ascii_in,
    non_string_key,
    only_when,
    repeats,
    reserved_extension,
    unknown_key,
)
from urim.schema_gen import EXTENSION, FORMATS

Path = tuple["str | int", ...]

_PLAIN = re.compile(r"[A-Za-z0-9_./-]+")


def path_text(path: Path) -> str:
    """``questions.team.options``, ``targets["a b"]``, ``levels[0]``; every key is sanitized (C-089)."""
    out = ""
    for seg in path:
        if isinstance(seg, int):
            out += f"[{seg}]"
        elif _PLAIN.fullmatch(seg):
            out += seg if out == "" else f".{seg}"
        else:
            escaped = seg.replace("\\", "\\\\").replace('"', '\\"')
            out += f'["{sanitize(escaped)}"]'
    return out


def _must_be(path: Path, desc: str) -> Failure:
    return Failure(must_be(path_text(path), desc))


def _kind(value: object) -> str:
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, list):
        return "sequence"
    return "null"


#: The YAML kind each schema leaf accepts; `alt` picks its option by this (a table, so every
#: leaf type has an entry even though today's schema only puts some of them in an `alt`).
_ACCEPTS: dict[type[Leaf], str] = {
    Str: "string",
    Enum: "string",
    Int: "number",
    Num: "number",
    Bool: "boolean",
    List: "sequence",
    Map: "mapping",
    Obj: "mapping",
    One: "mapping",
    Opaque: "mapping",
}


def _accepts(node: Leaf) -> str:
    return _ACCEPTS[type(node)]


def _ascii_and_visible(path: Path, s: str) -> None:
    if has_invisible(s):
        raise Failure(invisible_in(path_text(path)))
    if not s.isascii():
        raise Failure(non_ascii_in(path_text(path)))


def check_string(path: Path, value: object, fmt: Fmt, desc: str) -> str:
    """Check a string of format ``fmt``: invisible (C-088), then non-ASCII (C-092), then the format."""
    if not isinstance(value, str) or value == "":
        raise _must_be(path, desc)
    if fmt not in ("string", "expr"):
        _ascii_and_visible(path, value)
    if not matches(fmt, value):
        raise _must_be(path, desc)
    return value


def _mapping(path: Path, value: object, desc: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _must_be(path, desc)
    if not all(isinstance(k, str) for k in value):
        raise Failure(non_string_key(path_text(path)))
    return {str(k): v for k, v in value.items()}


def _extension_key(path: Path, key: str) -> None:
    """Check an ``x-<provider>`` key at a position that allows one (SPEC §5.11.1, §5.11.2)."""
    check_string(path, key, "x_key", FORMATS["x_key"])
    if key.startswith("x-urim-"):
        raise Failure(reserved_extension(path_text(path)))


def _variant_fields(
    node: Obj, mapping: dict[str, object], path: Path
) -> tuple[tuple[Field, ...], dict[str, list[str]]]:
    """Check the tag value; return the fields it allows and, per other-variant key, its variants."""
    fields = node.fields
    others: dict[str, list[str]] = {}
    tag = node.tag
    if tag is not None:
        tag_value = mapping.get(tag.field)
        for f in node.fields:
            if f.name == tag.field and tag.field in mapping:
                _check(f.node, tag_value, (*path, f.name))
        for variant, extra in tag.variants:
            if tag.field not in mapping or variant == tag_value:
                fields = (*fields, *extra)
            else:
                for f in extra:
                    others.setdefault(f.name, []).append(variant)
    return fields, others


def _check_object(node: Obj, value: object, path: Path) -> None:
    mapping = _mapping(path, value, node.desc)
    fields, others = _variant_fields(node, mapping, path)
    tag = node.tag
    known = {f.name for f in fields}
    for key in mapping:
        if key in known:
            continue
        at = (*path, key)
        removed = dict(node.removed).get(key)
        if removed is not None:
            raise Failure(f"{path_text(at)} {removed}")
        variants = others.get(key)
        if variants is not None and tag is not None:
            raise Failure(only_when(path_text(at), tag.field, variants))
        if node.ext and key.startswith("x-"):
            _extension_key(at, key)
        else:
            raise Failure(unknown_key(path_text(at)))
    # Without a tag value only the shared fields are required; the missing tag is reported.
    required = fields if tag is not None and tag.field in mapping else node.fields
    missing = [f.name for f in required if f.req and f.name not in mapping]
    if missing:
        raise Failure(missing_keys_in(path_text(path), missing))
    by_name = {f.name: f for f in fields}
    for key, child in mapping.items():
        field = by_name.get(key)
        if field is None:
            _check(EXTENSION, child, (*path, key))
        elif tag is None or field.name != tag.field:
            _check(field.node, child, (*path, key))


def _check_key(path: Path, key: str, fmt: Fmt) -> None:
    """Check a mapping key of format ``fmt``: same order as a string value, with its own message."""
    _ascii_and_visible(path, key)
    if not matches(fmt, key):
        raise Failure(bad_key(path_text(path), FORMATS[fmt]))
    if fmt == "x_key" and key.startswith("x-urim-"):
        raise Failure(reserved_extension(path_text(path)))


def _check_number(node: Num, value: object, path: Path) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _must_be(path, node.desc)
    low = node.min is None or (value > node.min if node.min_open else value >= node.min)
    high = node.max is None or (value < node.max if node.max_open else value <= node.max)
    if not (low and high):
        raise _must_be(path, node.desc)


def _check_list(node: List, value: object, path: Path) -> None:
    if not isinstance(value, list) or len(value) < node.min:
        raise _must_be(path, node.desc)
    for i, item in enumerate(value):
        _check(node.items, item, (*path, i))
        first = value.index(item) if node.unique else i
        if first != i:
            raise Failure(repeats(path_text((*path, i)), path_text((*path, first))))


def _check_map(node: Map, value: object, path: Path) -> None:
    mapping = _mapping(path, value, node.desc)
    if len(mapping) < node.min:
        raise _must_be(path, node.desc)
    entries = {f.name: f for f in node.entries}
    for key, child in mapping.items():
        entry = entries.get(key)
        if entry is not None:
            _check(entry.node, child, (*path, key))
        else:
            _check_key((*path, key), key, node.key)
            _check(node.value, child, (*path, key))
    missing = [f.name for f in node.entries if f.req and f.name not in mapping]
    if missing:
        raise Failure(missing_keys_in(path_text(path), missing))


def _check_one(node: One, value: object, path: Path) -> None:
    mapping = _mapping(path, value, node.desc)
    forbid = dict(node.forbid)
    names = {f.name for f in node.keys}
    for key in mapping:
        if key in forbid:
            raise Failure(f"{path_text(path)} {forbid[key]}")
        if key not in names:
            raise Failure(unknown_key(path_text((*path, key))))
    if len(mapping) != 1:
        raise _must_be(path, node.desc)
    for f in node.keys:
        if f.name in mapping:
            _check(f.node, mapping[f.name], (*path, f.name))


def _check(node: Node, value: object, path: Path) -> None:  # noqa: PLR0912 - one branch per kind
    if isinstance(node, Str):
        check_string(path, value, node.fmt, node.desc)
    elif isinstance(node, Int):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or (node.min is not None and value < node.min)
        ):
            raise _must_be(path, node.desc)
    elif isinstance(node, Num):
        _check_number(node, value, path)
    elif isinstance(node, Bool):
        if not isinstance(value, bool):
            raise _must_be(path, node.desc)
    elif isinstance(node, Enum):
        if value not in node.values:
            raise _must_be(path, node.desc)
    elif isinstance(node, List):
        _check_list(node, value, path)
    elif isinstance(node, Map):
        _check_map(node, value, path)
    elif isinstance(node, Obj):
        _check_object(node, value, path)
    elif isinstance(node, One):
        _check_one(node, value, path)
    elif isinstance(node, Alt):
        kind = _kind(value)
        option = next((o for o in node.options if _accepts(o) == kind), None)
        if option is None:
            raise _must_be(path, node.desc)
        _check(option, value, path)
    else:
        mapping = _mapping(path, value, node.desc)
        if not mapping:
            raise _must_be(path, node.desc)


def validate(node: Node, value: object) -> None:
    """Check ``value`` (a document root) against ``node``; raises ``Failure`` with the first problem."""
    _check(node, value, ())


__all__ = ["Field", "Path", "check_string", "path_text", "validate"]
