// Test-only provider: a made-up vendor that speaks the systemone body. Tests use it instead of a real vendor id.
// Registered into DESCRIPTORS on import so the client resolves it like any shipped descriptor. Never shipped.
import { DESCRIPTORS, GENERIC_ERRORS, type Descriptor } from "../src/index.ts";

export const FAKE_PROVIDER = "fake-systemone";
export const FAKE_ENV = "FAKE_SYSTEMONE_API_KEY";

const fake: Descriptor = {
  provider: FAKE_PROVIDER, camp: "systemone", url: "https://systemone.example.test/v1/systemone",
  auth: [{ header: "authorization", scheme: "Bearer", env: FAKE_ENV }], modelNaming: "registry",
  models: {
    "jev@1.14.0": { wire: "jev-1.14.0", answeredAs: ["jev-1.14.0"] },
    "jev@1.13.0": { wire: "jev-1.13.0", answeredAs: ["jev-1.13.0"] },
    "jev-latest": { wire: "jev-latest", answeredAs: ["jev-1.14.0"] },
    "jev-preview": { wire: "jev-preview", answeredAs: ["jev-1.14.0"] },
  },
  servedModelHeader: null, requestIdHeader: null,
  errors: { ...GENERIC_ERRORS, byStatus: { ...GENERIC_ERRORS.byStatus, 529: "provider_unavailable" } },
  sources: [],
};
export const FAKE_SYSTEMONE: Descriptor = Object.freeze(fake);

(DESCRIPTORS as Record<string, Descriptor>)[FAKE_PROVIDER] ??= FAKE_SYSTEMONE;
