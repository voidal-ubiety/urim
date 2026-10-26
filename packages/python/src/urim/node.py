"""Schema node types: the shape of the generated data in schema_gen.py (same as node.ts/schema.rs).

Implements: C-095
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Fmt = Literal[
    "string",
    "expr",
    "id",
    "target_id",
    "capability_path",
    "semver",
    "semver_range",
    "protocol_version",
    "hash",
    "integrity",
    "timestamp",
    "x_key",
    "confidence_ref",
]

Pairs = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class Field:
    """A named key of an object, a map entry, or a one-of choice."""

    name: str
    node: Node
    req: bool


@dataclass(frozen=True, slots=True)
class Tag:
    """The key whose value selects extra fields (``type: choice`` adds ``options``)."""

    field: str
    variants: tuple[tuple[str, tuple[Field, ...]], ...]


@dataclass(frozen=True, slots=True)
class Str:
    """A non-empty string of a format."""

    fmt: Fmt
    desc: str


@dataclass(frozen=True, slots=True)
class Int:
    """An integer, optionally with a minimum."""

    min: int | None
    desc: str


@dataclass(frozen=True, slots=True)
class Num:
    """A finite number in an optional range."""

    min: float | None
    max: float | None
    desc: str
    min_open: bool
    max_open: bool


@dataclass(frozen=True, slots=True)
class Bool:
    """True or false."""

    desc: str


@dataclass(frozen=True, slots=True)
class Enum:
    """One of fixed strings."""

    values: tuple[str, ...]
    desc: str


@dataclass(frozen=True, slots=True)
class List:
    """A sequence of ``items``, at least ``min`` long, optionally without repeats."""

    items: Node
    min: int
    desc: str
    unique: bool


@dataclass(frozen=True, slots=True)
class Map:
    """A mapping with keys of format ``key``; ``entries`` are keys with their own types."""

    key: Fmt
    value: Node
    min: int
    entries: tuple[Field, ...]
    desc: str


@dataclass(frozen=True, slots=True)
class Obj:
    """A closed mapping: known fields only, plus ``x-`` keys when ``ext``."""

    fields: tuple[Field, ...]
    tag: Tag | None
    removed: Pairs
    desc: str
    ext: bool


@dataclass(frozen=True, slots=True)
class One:
    """A mapping with exactly one of ``keys``."""

    keys: tuple[Field, ...]
    forbid: Pairs
    desc: str


@dataclass(frozen=True, slots=True)
class Opaque:
    """A non-empty mapping whose contents this checker does not read."""

    desc: str


Leaf = Str | Int | Num | Bool | Enum | List | Map | Obj | One | Opaque


@dataclass(frozen=True, slots=True)
class Alt:
    """The first option that accepts the value's YAML kind; options never nest."""

    options: tuple[Leaf, ...]
    desc: str


Node = Leaf | Alt
