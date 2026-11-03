"""Test-only provider: a made-up vendor that speaks the systemone body (mirror of urim-ts test/fake-systemone.ts).
Registered into DESCRIPTORS on import so the client resolves it like any shipped descriptor. Never shipped."""

from typing import Any, cast

from urim.descriptors import DESCRIPTORS, GENERIC_ERRORS, AuthSpec, Descriptor, ErrorMap, ModelSpec

FAKE_PROVIDER = "fake-systemone"
FAKE_ENV = "FAKE_SYSTEMONE_API_KEY"

FAKE_SYSTEMONE = Descriptor(
    FAKE_PROVIDER,
    "systemone",
    "https://systemone.example.test/v1/systemone",
    (AuthSpec("authorization", "Bearer", FAKE_ENV),),
    ErrorMap({**GENERIC_ERRORS.by_status, 529: "provider_unavailable"}),
    models={
        "jev@1.14.0": ModelSpec("jev-1.14.0", ("jev-1.14.0",)),
        "jev@1.13.0": ModelSpec("jev-1.13.0", ("jev-1.13.0",)),
        "jev-latest": ModelSpec("jev-latest", ("jev-1.14.0",)),
        "jev-preview": ModelSpec("jev-preview", ("jev-1.14.0",)),
    },
)

cast(dict[str, Any], DESCRIPTORS).setdefault(FAKE_PROVIDER, FAKE_SYSTEMONE)
