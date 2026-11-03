"""A/C: schema adapters behind the D9 barrier {parse, to_json_schema}.

- ``json_schema_adapter``: zero-dependency adapter for a hand-written JSON Schema + validator function.
- ``pydantic_schema``: optional; Pydantic v2 is imported lazily, so it is not a required runtime dependency.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .errors import Issue
from .types import ParseFail, ParseOk


@dataclass(frozen=True)
class _Adapter:
    _parse: Callable[[Any], ParseOk | ParseFail]
    _schema: Callable[[], Any]

    def parse(self, value: Any) -> ParseOk | ParseFail:
        return self._parse(value)

    def to_json_schema(self) -> Any:
        return self._schema()


def json_schema_adapter(schema: Any, validate: Callable[[Any], list[Issue]]) -> _Adapter:
    def parse(v: Any) -> ParseOk | ParseFail:
        issues = validate(v)
        return ParseFail(tuple(issues)) if issues else ParseOk(v)

    return _Adapter(parse, lambda: schema)


def pydantic_schema(model: type) -> _Adapter:
    """Adapt a Pydantic v2 BaseModel. parse returns the model's JSON-mode dict (plain data, D9)."""
    from pydantic import ValidationError  # lazy: optional extra

    def parse(v: Any) -> ParseOk | ParseFail:
        try:
            return ParseOk(model.model_validate(v).model_dump(mode="json"))  # type: ignore[attr-defined]
        except ValidationError as e:
            return ParseFail(tuple(Issue(".".join(map(str, err["loc"])) or "$", err["msg"]) for err in e.errors()))

    return _Adapter(parse, lambda: model.model_json_schema())  # type: ignore[attr-defined]
