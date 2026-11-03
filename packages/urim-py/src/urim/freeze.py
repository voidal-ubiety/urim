"""C: deep freeze for data we hand out (C18): dict -> read-only mapping view, list -> tuple."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def deep_freeze(v: Any) -> Any:
    if isinstance(v, Mapping):
        return MappingProxyType({k: deep_freeze(x) for k, x in v.items()})
    if isinstance(v, (list, tuple)):
        return tuple(deep_freeze(x) for x in v)
    return v


def thaw(v: Any) -> Any:
    """Read-only views back to plain JSON values (for serialization and comparisons)."""
    if isinstance(v, Mapping):
        return {k: thaw(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [thaw(x) for x in v]
    return v
