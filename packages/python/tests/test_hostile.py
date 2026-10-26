"""C-085, C-091: in-process guarantees behind the hostile-input suite (scripts/hostile.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from urim import profile
from urim.check import check_text

HOSTILE = Path(__file__).resolve().parents[3] / "fixtures" / "hostile"
# The file the gadget fixtures try to create; one source, shared with scripts/hostile.py.
CANARY = Path(json.loads((HOSTILE.parent / "hostile.json").read_text(encoding="utf-8"))["canary"])
GADGETS = [
    "gadget-python-object-apply.lock",
    "gadget-python-name.lock",
    "gadget-python-object-new.lock",
    "gadget-js-function.lock",
    "gadget-js-undefined-regexp.lock",
    "gadget-ruby-object.lock",
]


def test_c085_loader_is_a_safe_loader_with_no_python_constructors() -> None:
    loader = profile._CoreLoader
    assert issubclass(loader, yaml.SafeLoader)
    assert not issubclass(loader, (yaml.FullLoader, yaml.UnsafeLoader))
    tags = [*loader.yaml_constructors, *loader.yaml_multi_constructors]
    assert not [t for t in tags if t and "python" in t]


@pytest.mark.parametrize("name", GADGETS)
def test_c085_gadget_is_rejected_and_nothing_executes(name: str) -> None:
    text = (HOSTILE / name).read_text(encoding="utf-8")
    assert check_text(name, text).line == f"{name}: error: tags are not allowed"
    # Defence in depth: even bypassing the event check, the loader cannot build the gadget.
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.load(text, Loader=profile._CoreLoader)  # noqa: S506 - the loader under test
    assert not CANARY.exists()


def test_c091_proto_keys_are_ordinary_keys() -> None:
    text = (HOSTILE / "proto-pollution-nested.lock").read_text(encoding="utf-8")
    assert check_text("p.lock", text).line == "p.lock: ok (lockfile, hoshen 2, urim x)"
    value = profile.parse_document(text)
    assert isinstance(value, dict)
    assert list(value) == ["hoshen", "urim", "__proto__", "constructor", "prototype", "q"]
    assert value["hoshen"] == 2  # the smuggled `hoshen: 3` stayed nested
