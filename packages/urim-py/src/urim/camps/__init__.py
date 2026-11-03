"""C: camp dispatch. URL, wire model, error map, aliases and request-id header all come from descriptor data."""

from __future__ import annotations

from typing import Any, Protocol

from ..classify import classify_vendor_reply
from ..descriptors import descriptor_for, explicit_model_spec, header, model_spec_for
from ..errors import UrimError
from ..types import Definition, Tier, WireReply, WireRequest
from . import decisions, systemone
from .shared import Decoded, DecodedFail, DecodedOk, TokenUsage

__all__ = ["Decoded", "DecodedFail", "DecodedOk", "TokenUsage", "decode_reply", "encode_request", "request_id_of"]


class _Codec(Protocol):
    PATH: str

    def encode(self, d: Definition, wire: str, input: Any) -> Any: ...
    def decode(self, d: Definition, tier: Tier, body: Any, *, unavailable_sentinel: bool = False) -> Decoded: ...


def _codec(tier: Tier) -> _Codec:
    return systemone if tier.camp == "systemone" else decisions


def encode_request(d: Definition, tier: Tier, input: Any) -> WireRequest:
    desc = descriptor_for(tier)
    wire = model_spec_for(desc, tier).wire
    codec = _codec(tier)
    return WireRequest(tier.id, tier.camp, codec.PATH, desc.url.replace("{model}", wire), codec.encode(d, wire, input))


def request_id_of(tier: Tier, reply: WireReply) -> str | None:
    name = descriptor_for(tier).request_id_header
    return None if name is None else header(reply.headers, name)


def _with_request_id(e: UrimError, rid: str | None) -> UrimError:
    if rid is None or e.request_id is not None:
        return e
    return UrimError(
        e.type,
        e.message,
        tier=e.tier,
        status=e.status,
        request_id=rid,
        retry_after_ms=e.retry_after_ms,
        issues=e.issues,
        cause=e.__cause__,
    )


def decode_reply(d: Definition, tier: Tier, reply: WireReply) -> Decoded:
    desc = descriptor_for(tier)
    rid = request_id_of(tier, reply)
    failure = classify_vendor_reply(desc, reply)
    if failure.type is not None:
        return DecodedFail(
            UrimError(
                failure.type,
                f"HTTP {reply.status} from {tier.id}",
                tier=tier.id,
                status=reply.status,
                request_id=rid,
                retry_after_ms=failure.retry_after_ms,
            )
        )
    decoded = _codec(tier).decode(d, tier, reply.body, unavailable_sentinel=desc.confidence_unavailable_sentinel)
    if isinstance(decoded, DecodedFail):
        return DecodedFail(_with_request_id(decoded.error, rid))
    # Only tiers with an explicit descriptor model row are checked (accepted 2026-10-28).
    spec = explicit_model_spec(desc, tier)
    if spec is not None and decoded.model is not None and decoded.model not in spec.answered_as:
        return DecodedFail(
            UrimError(
                "lock_violation", f'{tier.id} was answered by model "{decoded.model}"', tier=tier.id, request_id=rid
            )
        )
    return decoded
