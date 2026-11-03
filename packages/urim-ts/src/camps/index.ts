// C: camp dispatch. The camp is the tier's (checked against its descriptor at define time); the URL,
// wire model, error map, aliases and request-id header all come from descriptor data.
import { UrimError } from "../errors.ts";
import { classifyVendorReply } from "../classify.ts";
import { descriptorFor, header, modelSpecFor } from "../descriptors.ts";
import type { Definition, Tier, WireReply, WireRequest } from "../types.ts";
import * as decisions from "./decisions.ts";
import * as systemone from "./systemone.ts";
import type { Decoded } from "./shared.ts";

export type { Decoded, TokenUsage } from "./shared.ts";

const codec = (tier: Tier) => (tier.camp === "systemone" ? systemone : decisions);

export const encodeRequest = (def: Definition, tier: Tier, input: unknown): WireRequest => {
  const camp = codec(tier);
  const d = descriptorFor(tier);
  const wire = modelSpecFor(d, tier).wire;
  return { tierId: tier.id, camp: tier.camp, path: camp.PATH, url: d.url.replace("{model}", wire), body: camp.encode(def, wire, input) };
};

/** Request id from the vendor's documented header only; undefined when the vendor documents none. */
export const requestIdOf = (tier: Tier, reply: WireReply): string | undefined => {
  const name = descriptorFor(tier).requestIdHeader;
  return name === null ? undefined : header(reply.headers, name);
};

const withRequestId = (e: UrimError, requestId: string | undefined): UrimError =>
  requestId === undefined || e.requestId !== undefined ? e
    : new UrimError(e.type, e.message, { tier: e.tier ?? "", requestId,
      ...(e.status === undefined ? {} : { status: e.status }), ...(e.retryAfterMs === undefined ? {} : { retryAfterMs: e.retryAfterMs }),
      ...(e.issues === undefined ? {} : { issues: e.issues }), ...(e.cause === undefined ? {} : { cause: e.cause }) });

export const decodeReply = (def: Definition, tier: Tier, reply: WireReply): Decoded => {
  const d = descriptorFor(tier);
  const requestId = requestIdOf(tier, reply);
  const failure = classifyVendorReply(d, reply);
  if (failure.type !== null) {
    return { ok: false, error: new UrimError(failure.type, `HTTP ${reply.status} from ${tier.id}`, { tier: tier.id, status: reply.status,
      ...(requestId === undefined ? {} : { requestId }), ...(failure.retryAfterMs === undefined ? {} : { retryAfterMs: failure.retryAfterMs }) }) };
  }
  const decoded = codec(tier).decode(def, tier, reply.body, { unavailableSentinel: d.confidenceUnavailableSentinel === true });
  if (!decoded.ok) return { ok: false, error: withRequestId(decoded.error, requestId) };
  // Only tiers with an explicit descriptor model row are checked; no row = no documented alias list (no false alarms).
  // The served-model header (Fastino) is not compared: its value format is undocumented. TODO(vendor-fact)
  const spec = d.models[`${tier.model}@${tier.version}`] ?? d.models[tier.model];
  const stray = spec !== undefined && decoded.model !== null && !spec.answeredAs.includes(decoded.model) ? decoded.model : undefined;
  if (stray !== undefined) {
    return { ok: false, error: new UrimError("lock_violation", `${tier.id} was answered by model "${stray}"`, {
      tier: tier.id, ...(requestId === undefined ? {} : { requestId }) }) };
  }
  return decoded;
};
