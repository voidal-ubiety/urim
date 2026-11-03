"""D: provider descriptors. Pure data, one row per vendor, mirrored from urim-ts src/descriptors.ts, whose values
come from public vendor docs (checked 2026-10-28 EDT). Camp is chosen by BODY vocabulary, never
by URL path. Unknowns are None and tagged TODO(vendor-fact); None means "use the conservative generic behaviour".
A cross-port test checks this table against the TS one field by field.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Literal

from .errors import ErrorType
from .types import Camp, Tier


@dataclass(frozen=True)
class AuthSpec:
    header: str
    scheme: Literal["Bearer"] | None
    env: str  # the NAME of the variable; its value is read at send time only


@dataclass(frozen=True)
class ModelSpec:
    wire: str
    answered_as: tuple[str, ...]


@dataclass(frozen=True)
class CodeRule:
    status: int
    codes: Mapping[str, ErrorType]


@dataclass(frozen=True)
class ErrorMap:
    by_status: Mapping[int, ErrorType]
    by_code: tuple[CodeRule, ...] = ()
    retry_headers: tuple[str, ...] = ("retry-after",)


@dataclass(frozen=True)
class Descriptor:
    provider: str
    camp: Camp
    url: str
    auth: tuple[AuthSpec, ...]
    errors: ErrorMap
    model_naming: Literal["registry", "deployment"] = "registry"
    models: Mapping[str, ModelSpec] = field(default_factory=dict)
    served_model_header: str | None = None
    request_id_header: str | None = None
    sources: tuple[str, ...] = ()
    #: Set only for a provider documented to send confidence 0 + empty probabilities as "unavailable" (e.g. a
    #: gateway); such answers then decode as confidence None. No shipped descriptor sets it.
    confidence_unavailable_sentinel: bool = False


_GENERIC_STATUS: dict[int, ErrorType] = {401: "auth", 403: "auth", 408: "timeout", 429: "rate_limited", 504: "timeout"}
GENERIC_ERRORS = ErrorMap(by_status=_GENERIC_STATUS)


def _bearer(env: str) -> AuthSpec:
    return AuthSpec("authorization", "Bearer", env)


def _m(wire: str, *answered: str) -> ModelSpec:
    return ModelSpec(wire, answered)


_QUOTA: dict[str, ErrorType] = {
    c: "quota_exceeded"
    for c in (
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    )
}

DESCRIPTORS: Mapping[str, Descriptor] = {
    "typesafe": Descriptor(
        "typesafe",
        "systemone",
        "https://api.typesafe.ai/v1/systemone",
        (_bearer("TYPESAFE_API_KEY"),),
        ErrorMap({**_GENERIC_STATUS, 529: "provider_unavailable"}),  # S3
        models={
            "jev@1.14.0": _m("jev-1.14.0", "jev-1.14.0"),
            "jev@1.13.0": _m("jev-1.13.0", "jev-1.13.0"),
            "jev-latest": _m("jev-latest", "jev-1.14.0"),
            "jev-preview": _m("jev-preview", "jev-1.14.0"),
        },
        request_id_header=None,  # TODO(vendor-fact): header name unknown; SDK exposes result.request_id (S6)
        sources=(
            "https://docs.typesafe.ai/api/system-one",
            "https://docs.typesafe.ai/models",
            "https://docs.typesafe.ai/api/errors.md",
        ),
    ),
    "openai": Descriptor(
        "openai",
        "decisions",
        "https://api.openai.com/v1/decisions",
        (_bearer("OPENAI_API_KEY"),),
        ErrorMap({**_GENERIC_STATUS, 503: "provider_unavailable"}, (CodeRule(429, _QUOTA),)),  # O4
        models={"gpt-6-luna": _m("gpt-6-luna", "gpt-6-luna")},
        request_id_header="x-request-id",  # O1, O5
        sources=(
            "https://developers.openai.com/api/reference/typescript/resources/decisions/methods/create/index.md",
            "https://developers.openai.com/api/docs/guides/error-codes.md",
            "https://developers.openai.com/api/reference/overview.md",
        ),
    ),
    "microsoft": Descriptor(
        "microsoft",
        "systemone",
        "{endpoint}/providers/microsoft/v1/systemone",
        (AuthSpec("api-key", None, "AZURE_API_KEY"), _bearer("AZURE_ENTRA_TOKEN")),  # Entra env name is OUR choice
        GENERIC_ERRORS,
        model_naming="deployment",  # TODO(vendor-fact): request id, quota vs rate
        sources=(
            "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision",
        ),
    ),
    "cloudflare": Descriptor(
        "cloudflare",
        "systemone",
        "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/cloudflare/{model}",
        (_bearer("CLOUDFLARE_AUTH_TOKEN"),),
        GENERIC_ERRORS,  # TODO(vendor-fact): REST envelope, errors, request id
        models={"clef": _m("clef", "clef"), "clef-flash": _m("clef-flash", "clef-flash")},
        sources=("https://developers.cloudflare.com/workers-ai/models/clef/",),
    ),
    "liquid": Descriptor(
        "liquid",
        "systemone",
        "https://api.liquid.ai/decisions/v1/systemone",
        (_bearer("LIQUID_API_KEY"),),
        GENERIC_ERRORS,
        sources=("https://docs.liquid.ai/lfm/models/d1",),
    ),  # TODO(vendor-fact)
    "perplexity": Descriptor(
        "perplexity",
        "systemone",
        "https://api.perplexity.ai/v1/decisions",
        (_bearer("PERPLEXITY_API_KEY"),),
        GENERIC_ERRORS,  # P1: branch on status, not code
        models={
            "pplx-decider-latest": _m("pplx-decider-latest", "pplx-decider-v1.2"),
            "pplx-decider-flash-latest": _m("pplx-decider-flash-latest", "pplx-decider-flash-v1.2"),
        },
        request_id_header="x-request-id",
        sources=("https://docs.perplexity.ai/api-reference/decisions-post",),
    ),
    "fastino": Descriptor(
        "fastino",
        "systemone",
        "https://api.fastino.ai/v1/systemone",
        (AuthSpec("x-api-key", None, "FASTINO_API_KEY"), _bearer("FASTINO_API_KEY")),
        ErrorMap(
            {**_GENERIC_STATUS, 402: "quota_exceeded", 425: "provider_unavailable"},
            (),
            ("retry-after", "x-should-retry"),
        ),  # F1
        models={"GLiDE": _m("fastino/GLiDE", "glide", "fastino/GLiDE")},  # F2
        served_model_header="x-fastino-served-model",  # TODO(vendor-fact): request id
        sources=("https://docs.fastino.ai/openapi.json", "https://docs.fastino.ai/inference/systemone.md"),
    ),
    "inception": Descriptor(
        "inception",
        "systemone",
        "https://api.inceptionlabs.ai/v1/decisions",
        (_bearer("INCEPTION_API_KEY"),),
        GENERIC_ERRORS,
        sources=("https://docs.inceptionlabs.ai/capabilities/decisions.md",),
    ),  # TODO(vendor-fact)
}


def descriptor_for(tier: Tier) -> Descriptor:
    d = DESCRIPTORS.get(tier.provider)
    return d if d is not None else Descriptor(tier.provider, tier.camp, "", (), GENERIC_ERRORS)


def model_spec_for(d: Descriptor, tier: Tier) -> ModelSpec:
    return (
        d.models.get(f"{tier.model}@{tier.version}") or d.models.get(tier.model) or ModelSpec(tier.model, (tier.model,))
    )


def explicit_model_spec(d: Descriptor, tier: Tier) -> ModelSpec | None:
    return d.models.get(f"{tier.model}@{tier.version}") or d.models.get(tier.model)


def header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header read."""
    return next((v for k, v in headers.items() if k.lower() == name), None)


__all__ = [
    "DESCRIPTORS",
    "GENERIC_ERRORS",
    "AuthSpec",
    "CodeRule",
    "Descriptor",
    "ErrorMap",
    "ModelSpec",
    "descriptor_for",
    "header",
    "model_spec_for",
    "replace",
]
