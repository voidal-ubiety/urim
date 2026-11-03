"""urim (Python port). Same canonical JSON, hashes and envelope as the TypeScript port."""

from .camps import decode_reply, encode_request, request_id_of
from .canonical import canonicalize, sha256
from .classify import classify_reply, classify_vendor_reply
from .client import Client, create_client
from .cuts import resolve_cuts
from .define import choice, define_decision, noul, score, threshold, tier
from .descriptors import DESCRIPTORS, GENERIC_ERRORS, descriptor_for, model_spec_for
from .emit import emit
from .envelope import build_envelope
from .envelope_read import read_envelope
from .errors import FAILOVER_TYPES, Issue, UrimError
from .fit import estimate_fit_cost, parse_cases, run_fit
from .lock import parse_lock, serialize_lock
from .plan import estimate_input_tokens, explain, next_step, plan_attempts
from .schema import json_schema_adapter, pydantic_schema
from .types import CONFIDENCE_RULE, Objective

__all__ = [
    "CONFIDENCE_RULE",
    "DESCRIPTORS",
    "FAILOVER_TYPES",
    "GENERIC_ERRORS",
    "Client",
    "Issue",
    "Objective",
    "UrimError",
    "build_envelope",
    "canonicalize",
    "choice",
    "classify_reply",
    "classify_vendor_reply",
    "create_client",
    "decode_reply",
    "define_decision",
    "descriptor_for",
    "emit",
    "encode_request",
    "estimate_fit_cost",
    "estimate_input_tokens",
    "explain",
    "json_schema_adapter",
    "model_spec_for",
    "next_step",
    "noul",
    "parse_cases",
    "parse_lock",
    "plan_attempts",
    "pydantic_schema",
    "read_envelope",
    "request_id_of",
    "resolve_cuts",
    "run_fit",
    "score",
    "serialize_lock",
    "sha256",
    "threshold",
    "tier",
]
