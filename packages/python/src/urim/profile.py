"""The Urim YAML profile: text to a root value, rejecting what the profile forbids.

Same rules and order as profile.rs and profile.ts:

1. size limit (C-080), then profile characters only (``c-printable`` without NEL, LS, PS or a
   non-leading U+FEFF) (C-082);
2. well-formedness, in stream order: nesting deeper than ``MAX_DEPTH`` (C-083) is reported if
   it comes before the first syntax error, undefined alias or second document (C-020, C-022);
   those are ``invalid YAML``;
3. profile violations over the complete event stream, first in stream order: an anchor or
   alias (C-084), a tag (C-085), a ``<<`` key (C-086), an invisible character in a key
   (C-087). Anchor beats tag on the same node (C-090);
4. duplicate keys, collection keys, integers outside 64-bit range: invalid YAML (C-021, C-023,
   C-024).

The event pass is iterative, so no input can exhaust the Python stack; values are built only
after it succeeds, from depth-bounded input. Only plain ``dict``/``list``/scalars are built:
no constructor runs user-chosen code (tags are refused first, C-085).

Implements: C-014, C-020..C-028, C-080, C-082..C-087, C-090
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from urim.display import has_invisible, is_profile_char
from urim.limits import MAX_BYTES, MAX_DEPTH
from urim.problem import (
    ANCHOR_OR_ALIAS,
    INVALID_YAML,
    INVISIBLE_IN_KEY,
    MERGE_KEY,
    TAG,
    TOO_DEEP,
    TOO_LARGE,
    Failure,
)


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
    # A float needs a dot or an exponent: `01` matches neither resolver and stays a string
    # (C-027), as in JS and Rust (bug B-4).
    re.compile(
        r"^(?:[-+]?(?:\.[0-9]+|[0-9]+\.[0-9]*)(?:[eE][-+]?[0-9]+)?"
        r"|[-+]?[0-9]+[eE][-+]?[0-9]+"
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
        raise Failure(INVALID_YAML)
    return number


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    # Python treats True == 1 == 1.0 as the same dict key; YAML does not. Compare keys by
    # (type, value) so they only count as duplicates when the YAML type matches. Only str keys
    # are looked up afterwards, and a str never collides with a bool/int/float.
    seen: set[tuple[type, Any]] = set()
    for key_node, value_node in node.value:
        if not isinstance(key_node, yaml.ScalarNode):
            raise Failure(INVALID_YAML)
        key = loader.construct_object(key_node, deep=True)
        if (type(key), key) in seen:
            raise Failure(INVALID_YAML)
        seen.add((type(key), key))
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_CoreLoader.add_constructor("tag:yaml.org,2002:int", _construct_int)
_CoreLoader.add_constructor("tag:yaml.org,2002:map", _construct_mapping)


def _check_properties(event: yaml.NodeEvent) -> None:
    """Anchors take precedence over tags on the same node."""
    if event.anchor is not None:
        raise Failure(ANCHOR_OR_ALIAS)
    if getattr(event, "tag", None) is not None:
        raise Failure(TAG)


def _well_formed(text: str) -> list[yaml.Event]:
    """Rule 2: parse the whole stream, stopping at the first depth or syntax problem."""
    events: list[yaml.Event] = []
    anchors: set[str] = set()
    depth = 0
    documents = 0
    try:
        for event in yaml.parse(text, Loader=_CoreLoader):
            if isinstance(event, yaml.DocumentStartEvent):
                if documents:
                    raise Failure(INVALID_YAML)
                documents = 1
            elif isinstance(event, yaml.CollectionStartEvent):
                if depth >= MAX_DEPTH:
                    raise Failure(TOO_DEEP)
                depth += 1
            elif isinstance(event, yaml.CollectionEndEvent):
                depth -= 1
            elif isinstance(event, yaml.AliasEvent) and event.anchor not in anchors:
                raise Failure(INVALID_YAML)
            if isinstance(event, yaml.NodeEvent) and event.anchor is not None:
                anchors.add(event.anchor)
            events.append(event)
    except yaml.scanner.ScannerError as error:
        if _too_deep_before(text, _token_start(error)):
            raise Failure(TOO_DEEP) from None
        raise
    return events


def _token_start(error: yaml.MarkedYAMLError) -> int:
    """Return where the failing token starts: the context mark when there is one."""
    marks = (error.context_mark, error.problem_mark)
    return min((mark.index for mark in marks if mark is not None), default=0)


def _too_deep_before(text: str, token_start: int) -> bool:
    """Report whether the text before a failing token already nests deeper than MAX_DEPTH.

    The scanner looks ahead along a flow line and can fail on a later token before it hands
    over the events of the collections opened in front of it, so the depth check would never
    see them. Re-parsing only the prefix restores stream order (C-090).
    """
    depth = 0
    try:
        for event in yaml.parse(text[:token_start], Loader=_CoreLoader):
            if isinstance(event, yaml.CollectionStartEvent):
                if depth >= MAX_DEPTH:
                    return True
                depth += 1
            elif isinstance(event, yaml.CollectionEndEvent):
                depth -= 1
    except yaml.YAMLError:
        pass
    return False


def _check_events(events: list[yaml.Event]) -> None:
    """Rule 3: profile violations over the complete event stream, first in stream order."""
    # One entry per open collection: [is_mapping, next_is_key].
    stack: list[list[bool]] = []

    def starts_key() -> bool:
        if stack and stack[-1][0]:
            is_key = stack[-1][1]
            stack[-1][1] = not is_key
            return is_key
        return False

    # No AliasEvent case: _well_formed rejects an undefined alias, and a defined alias
    # always follows its anchor, which _check_properties reports first.
    for event in events:
        if isinstance(event, yaml.ScalarEvent):
            _check_properties(event)
            if starts_key():
                if event.value == "<<":
                    raise Failure(MERGE_KEY)
                if has_invisible(event.value):
                    raise Failure(INVISIBLE_IN_KEY)
        elif isinstance(event, yaml.CollectionStartEvent):
            _check_properties(event)
            starts_key()
            stack.append([isinstance(event, yaml.MappingStartEvent), True])
        elif isinstance(event, yaml.CollectionEndEvent):
            stack.pop()


def parse_document(text: str) -> object:
    """Parse ``text`` as one Urim-profile document; the root may be any value."""
    if len(text.encode("utf-8", "surrogatepass")) > MAX_BYTES:
        raise Failure(TOO_LARGE)
    text = text.removeprefix("\ufeff")
    if not all(is_profile_char(ord(c)) for c in text):
        raise Failure(INVALID_YAML)
    try:
        _check_events(_well_formed(text))
        return yaml.load(text, Loader=_CoreLoader)  # noqa: S506 - restricted safe loader
    except (yaml.YAMLError, ValueError, TypeError):
        raise Failure(INVALID_YAML) from None
