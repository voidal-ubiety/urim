"""A (thin): the ``urim`` console command, at parity with urim-ts src/cli.ts.

Same argv and the same input files give the same exit code, the same stdout/stderr lines and the same file bytes
(shared-fixtures/cli.vectors.json). All I/O goes through ``CliIo`` so every command runs in memory under test;
``FsIo`` binds it to the real filesystem. No network code: ``fit`` runs only with ``--fake`` replies.

Exit codes: 0 done, 1 usage or failure, 2 ``fit`` stopped at the cost estimate because ``--yes`` was not given.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import json
import keyword
import math
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn, Protocol

from .boundary import parse_price_table, to_json
from .diff import line_diff
from .emit import emit
from .fit import FitOk, NeedsConfirmation, parse_cases, run_fit
from .jsonfmt import js_number, pretty_canonical, stringify
from .lock import serialize_lock
from .providers import generate_providers_py, generate_providers_ts, parse_registry
from .testing import fake_provider
from .types import Definition

USAGE = (
    "usage:",
    "  urim emit <module...> --out <dir>",
    "  urim fit <module> --cases <eval.jsonl> --fake <fake.json> --lock <out> [--prices <prices.json>] "
    "[--export <name>] [--yes] [--repeat N] [--report]",
    "  urim providers --registry <registry.json> --out <file.ts>",
)


class CliIo(Protocol):
    def read_text(self, path: str) -> str: ...
    def write_text(self, path: str, text: str) -> None: ...
    def exists(self, path: str) -> bool: ...
    def import_module(self, path: str) -> Mapping[str, Any]: ...
    def out(self, line: str) -> None: ...
    def err(self, line: str) -> None: ...
    def now(self) -> float: ...


class FsIo:
    """The real filesystem and stdout/stderr. Modules are ``.py`` paths or dotted import names."""

    def read_text(self, path: str) -> str:
        return Path(path).read_text("utf-8")

    def write_text(self, path: str, text: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8", newline="")

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def import_module(self, path: str) -> Mapping[str, Any]:
        return _exports(_load(path))

    def out(self, line: str) -> None:
        sys.stdout.write(f"{line}\n")

    def err(self, line: str) -> None:
        sys.stderr.write(f"{line}\n")

    def now(self) -> float:
        import time

        return time.time() * 1000


def _load(path: str) -> ModuleType:
    if not path.endswith(".py"):
        return importlib.import_module(path)
    spec = importlib.util.spec_from_file_location(Path(path).stem, Path(path).resolve())
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exports(m: ModuleType) -> dict[str, Any]:
    """Like an ES module's exports: ``__all__`` if declared, else every public name."""
    names: Sequence[str] = getattr(m, "__all__", None) or [n for n in vars(m) if not n.startswith("_")]
    return {n: getattr(m, n) for n in names}


class _Usage(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """argparse that never prints or exits by itself: any parse problem becomes the shared USAGE text."""

    def error(self, message: str) -> NoReturn:
        raise _Usage(message)


def _flag(p: argparse.ArgumentParser, *names: str) -> None:
    # TS rule: a value flag followed by nothing (or by another --flag) is present but has no value
    for n in names:
        p.add_argument(f"--{n}", dest=f"{n}_" if keyword.iskeyword(n) else n, nargs="?", const=True, default=None)


def _parser(cmd: str) -> argparse.ArgumentParser:
    p = _Parser(prog=f"urim {cmd}", add_help=False, allow_abbrev=False)
    p.add_argument("positional", nargs="*")
    _flag(p, "out", "cases", "fake", "lock", "prices", "export", "repeat", "registry", "import")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--report", action="store_true")
    return p


def _str(v: Any) -> str | None:
    return v if isinstance(v, str) else None


def _js(v: float | str | None) -> str:
    """How a JS template literal prints a number, string or null."""
    return "null" if v is None else v if isinstance(v, str) else js_number(v)


_JS_DECIMAL = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _js_number_of(s: str) -> float:
    """JS ``Number(s)`` for decimal text; anything else is NaN."""
    t = s.strip()
    return 0.0 if t == "" else float(t) if _JS_DECIMAL.match(t) else math.nan


def _slug(contract: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", contract)


def _definitions(mod: Mapping[str, Any]) -> list[Definition]:
    return [v for v in mod.values() if isinstance(v, Definition)]


_HELP = frozenset({"--help", "-h", "help"})


def _usage(io: CliIo) -> int:
    for line in USAGE:
        io.err(line)
    return 1


def _emit(a: argparse.Namespace, io: CliIo) -> int:
    out = _str(a.out)
    if out is None or not a.positional:
        return _usage(io)
    hashes: dict[str, str] = {}
    for path in a.positional:
        defs = _definitions(io.import_module(path))
        if not defs:
            io.err(f"{path}: no decision definitions exported")
            return 1
        for d in defs:
            e = emit(d)
            file = f"{out}/{_slug(d.contract)}.contract.json"
            text = pretty_canonical(e.document)
            before = io.read_text(file) if io.exists(file) else None
            if before == text:
                io.out(f"unchanged {file} {e.hash}")
            else:
                if before is not None:
                    io.out(f"changed {file}")
                    for line in line_diff(before, text):
                        io.out(line)
                io.write_text(file, text)
                io.out(f"wrote {file} {e.hash}")
            hashes[d.contract] = e.hash
    io.write_text(f"{out}/urim.hashes.json", pretty_canonical(hashes))
    return 0


def _fit(a: argparse.Namespace, io: CliIo) -> int:
    mod_path = a.positional[0] if a.positional else None
    cases_path, lock_path, fake_path = _str(a.cases), _str(a.lock), _str(a.fake)
    if mod_path is None or cases_path is None or lock_path is None:
        return _usage(io)
    if fake_path is None:
        io.err("fit: real provider adapters are not in this build; pass --fake <fake.json>")
        return 1
    mod = io.import_module(mod_path)
    name = _str(a.export)
    found = _definitions(mod)
    d = (found[0] if found else None) if name is None else mod.get(name)
    if not isinstance(d, Definition):
        io.err(f"fit: no decision definition in {mod_path}")
        return 1
    repeat = _js_number_of(_str(a.repeat) or "1")
    if not (math.isfinite(repeat) and repeat == int(repeat) and repeat >= 1):
        io.err("fit: --repeat must be a positive integer")
        return 1
    prices_path = _str(a.prices)
    prices = None if prices_path is None else parse_price_table(json.loads(io.read_text(prices_path)))
    script = json.loads(io.read_text(fake_path))
    cases = parse_cases(io.read_text(cases_path))
    now: Callable[[], float] = io.now
    r = asyncio.run(
        run_fit(
            d,
            cases,
            adapters=[fake_provider(script, cycle=True)],
            prices=prices,
            repeat=int(repeat),
            yes=a.yes,
            now=now,
        )
    )
    e = r.estimate
    total = "incomplete" if e.total is None else f"{_js(e.total)} {_js(e.currency)}"
    io.out(f"cost estimate: {total} for {len(cases)} cases x {int(repeat)} run(s) x {len(d.tiers)} tier(s)")
    for t, v in e.per_tier.items():
        io.out(f"  {t}: {_js(v)} {_js(e.currency)}")
    for t in e.unknown:
        io.out(f"  unknown price: {t} (not estimated)")
    if isinstance(r, NeedsConfirmation):
        io.out("refusing to call providers without --yes")
        return 2
    if a.report:
        io.out(stringify(to_json(r.report)))
    if not isinstance(r, FitOk):
        io.err(f"fit: objectives unmet: {', '.join(r.unmet)}; lock not written")
        return 1
    io.write_text(lock_path, serialize_lock(r.lock))
    io.out(f"wrote {lock_path}")
    return 0


def _providers(a: argparse.Namespace, io: CliIo) -> int:
    reg, out = _str(a.registry), _str(a.out)
    if reg is None or out is None:
        return _usage(io)
    registry = parse_registry(json.loads(io.read_text(reg)))
    generate = generate_providers_py if out.endswith(".py") else generate_providers_ts
    io.write_text(out, generate(registry, source=reg, import_from=_str(a.import_)))
    io.out(f"wrote {out}{' (EXAMPLE DATA)' if registry['example'] else ''}")
    return 0


_COMMANDS: dict[str, Callable[[argparse.Namespace, CliIo], int]] = {"emit": _emit, "fit": _fit, "providers": _providers}


def run(argv: Sequence[str], io: CliIo) -> int:
    """Run one command; returns the exit code."""
    cmd, rest = (argv[0], list(argv[1:])) if argv else ("", [])
    if cmd in _HELP or any(a in ("--help", "-h") for a in rest):
        for line in USAGE:
            io.out(line)
        return 0
    command = _COMMANDS.get(cmd)
    if command is None:
        return _usage(io)
    try:
        args, _unknown = _parser(cmd).parse_known_args(rest)  # TS ignores unknown flags too
    except _Usage:
        return _usage(io)
    try:
        return command(args, io)
    except Exception as e:
        io.err(f"urim {cmd}: {e}")
        return 1


def main(argv: Sequence[str] | None = None, io: CliIo | None = None) -> int:
    """Console entry point (``urim``)."""
    return run(sys.argv[1:] if argv is None else argv, io or FsIo())
