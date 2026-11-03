// Public surface. Network adapters are NOT exported here: opt in via the `./adapters` subpath.
export { UrimError, type ErrorType, type Issue } from "./errors.ts";
export { tier, noul, choice, score, threshold, defineDecision } from "./define.ts";
export { explain, nextStep, estimateInputTokens, type PlanOptions } from "./plan.ts";
export { classifyReply, classifyVendorReply } from "./classify.ts";
export { DESCRIPTORS, GENERIC_ERRORS, descriptorFor, modelSpecFor, type Descriptor, type AuthSpec, type ModelSpec, type ErrorMap } from "./descriptors.ts";
export { encodeRequest, decodeReply, requestIdOf, type Decoded, type TokenUsage } from "./camps/index.ts";
export { resolveCuts, type CutContext } from "./cuts.ts";
export { buildEnvelope, type EnvelopeParts } from "./envelope.ts";
export { fakeProvider, type Adapter, type FakeProvider, type FakeStep } from "./testing.ts";
export type * from "./types.ts";
export { CONFIDENCE_RULE } from "./types.ts";
export { createClient, missingAdapters, settledRecord, type Client, type ClientDeps, type DecideOptions } from "./client.ts";
export { canonicalize, sha256 } from "./canonical.ts";
export { emit, type Emitted } from "./emit.ts";
export { parseLock, serializeLock, type LockParse } from "./lock.ts";
export { readEnvelope, type EnvelopeRead } from "./envelope-read.ts";
