"""C: the ONE place Python snake_case meets the camelCase JSON urim-ts writes (contract, lock, envelope, settled).

Rules:
- Only dataclass attribute names are mapped. Mapping keys (question names, tier ids, threshold names, vendor
  ``native`` data, raw bodies) are user/vendor data and are never re-cased.
- ``json_name``: snake -> lowerCamel for every member (no exceptions since slice 7), plus keyword escapes (``from_``).
- ``ABSENT`` attributes are omitted; ``interpret_failed`` is written only when true (as in urim-ts).
"""

from __future__ import annotations

import dataclasses
import types as _pytypes
import typing
from collections.abc import Mapping
from functools import cache
from types import MappingProxyType
from typing import Any, Literal, TypeVar, Union

from .freeze import deep_freeze
from .types import ABSENT, PriceTable, _Absent

_T = TypeVar("_T")
_ESCAPES = {"from_": "from"}
_OMIT_IF_FALSE = frozenset({"interpret_failed"})


@cache
def json_name(attr: str) -> str:
    """The JSON member name for dataclass attribute ``attr``."""
    if attr in _ESCAPES:
        return _ESCAPES[attr]
    if "_" not in attr:
        return attr
    head, *rest = attr.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def _omitted(name: str, value: Any) -> bool:
    return value is ABSENT or (name in _OMIT_IF_FALSE and value is False)


def to_json(value: Any) -> Any:
    """Python data -> plain JSON-ready data with urim-ts member names."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            json_name(f.name): to_json(v)
            for f in dataclasses.fields(value)
            if not _omitted(f.name, v := getattr(value, f.name))
        }
    if isinstance(value, Mapping):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    return value


@cache
def _hints(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _convert(tp: Any, v: Any) -> Any:
    origin = typing.get_origin(tp)
    if origin in (Union, _pytypes.UnionType):
        args = [a for a in typing.get_args(tp) if a is not _Absent]
        if v is None and type(None) in args:
            return None
        concrete = [a for a in args if a is not type(None)]
        return _convert(concrete[0], v) if len(concrete) == 1 else deep_freeze(v)
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        return from_json(tp, v)
    if origin is tuple:
        (item, *_rest) = typing.get_args(tp)
        return tuple(_convert(item, x) for x in v)
    if origin in (Mapping, dict) or tp is Mapping:
        kv = typing.get_args(tp)
        return MappingProxyType({k: _convert(kv[1] if kv else Any, x) for k, x in v.items()})
    if origin is Literal or tp in (str, int, float, bool):
        return v
    return deep_freeze(v)


def from_json(cls: type[_T], data: Mapping[str, Any]) -> _T:
    """Plain JSON (already validated by its reader) -> frozen snake_case dataclass. Unknown members ignored."""
    dc: Any = cls  # a dataclass type; the checker cannot see that through a TypeVar
    hints = _hints(dc)
    kwargs = {}
    for f in dataclasses.fields(dc):
        key = json_name(f.name)
        if key in data:
            kwargs[f.name] = _convert(hints[f.name], data[key])
        elif f.default is dataclasses.MISSING:
            raise KeyError(f"{cls.__name__}: missing member {key!r}")
    return cls(**kwargs)


def parse_price_table(data: Mapping[str, Any]) -> PriceTable:
    """The shared PriceTable JSON (camelCase, as urim-ts) -> PriceTable."""
    return from_json(PriceTable, data)
