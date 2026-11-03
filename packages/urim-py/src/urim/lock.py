"""C: lockfile read/write (design §6), mirroring urim-ts src/lock.ts. Readers validate and ignore unknown keys;
the writer is strict. JSON member names come from ``urim.boundary`` only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard

from .boundary import from_json, json_name, to_json
from .errors import Issue, UrimError
from .jsonfmt import pretty_canonical
from .types import Lock, ParseFail, ParseOk


def _is_obj(v: Any) -> TypeGuard[Mapping[str, Any]]:
    return isinstance(v, Mapping)


def _is_hash(v: Any) -> bool:
    return isinstance(v, str) and v.startswith("sha256:") and len(v) > 7


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v: Any) -> bool:
    return _is_num(v) and float(v).is_integer()


def _issues(v: Mapping[str, Any]) -> list[Issue]:
    out: list[Issue] = []
    if not (v.get("lock") == 1 and _is_num(v.get("lock"))):
        out.append(Issue("lock", "unsupported lock format (expected 1)"))
    c = v.get("contract")
    if not (_is_obj(c) and isinstance(c.get("id"), str) and _is_hash(c.get("hash"))):
        out.append(Issue("contract", "needs {id: string, hash: sha256:...}"))
    cuts = v.get("cuts")
    if not _is_obj(cuts):
        out.append(Issue("cuts", "must be an object"))
    else:
        for name, per_tier in cuts.items():
            if not _is_obj(per_tier):
                out.append(Issue(f"cuts.{name}", "must be an object"))
                continue
            out += [
                Issue(f"cuts.{name}.{t}", "cutoff must be a number within 0..1")
                for t, n in per_tier.items()
                if not (_is_num(n) and 0 <= n <= 1)
            ]
    dh = json_name("descriptor_hash")
    tiers = v.get("tiers")
    if "tiers" in v and not (
        isinstance(tiers, list)
        and all(
            _is_obj(t) and isinstance(t.get("id"), str) and (t.get(dh, 0) is None or _is_hash(t.get(dh))) for t in tiers
        )
    ):
        out.append(Issue("tiers", "must be [{id, descriptorHash: sha256:...|null}]"))
    ev = v.get("eval")
    if "eval" in v and not (
        _is_obj(ev)
        and _is_hash(ev.get(json_name("set_hash")))
        and _is_int(ev.get("n"))
        and ev["n"] >= 0
        and _is_int(ev.get("repeat"))
        and ev["repeat"] >= 1
        and isinstance(ev.get("at"), str)
        and isinstance(ev.get(json_name("objectives_met")), bool)
    ):
        out.append(Issue("eval", "must be {setHash, n >= 0, repeat >= 1, at, objectivesMet}"))
    return out


def parse_lock(v: Any) -> ParseOk | ParseFail:
    """Lock JSON -> ParseOk(Lock) or ParseFail(issues). Same checks and issue paths as urim-ts parseLock."""
    if not _is_obj(v):
        return ParseFail((Issue("$", "lock must be an object"),))
    issues = _issues(v)
    return ParseFail(tuple(issues)) if issues else ParseOk(from_json(Lock, v))


def serialize_lock(lock: Lock) -> str:
    """Lock -> reviewable canonical text, byte-identical to urim-ts serializeLock. Refuses an invalid lock."""
    r = parse_lock(to_json(lock))
    if not r.ok:
        detail = "; ".join(f"{i.path}: {i.message}" for i in r.issues)
        raise UrimError("lock_violation", f"refusing to write invalid lock: {detail}", issues=r.issues)
    return pretty_canonical(to_json(r.value))
