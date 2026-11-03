// C: HTTP outcome -> closed error type. Generic column plus per-vendor maps carried as descriptor data.
import type { ErrorType } from "./errors.ts";
import { GENERIC_ERRORS, header, type Descriptor, type ErrorMap } from "./descriptors.ts";
import type { WireReply } from "./types.ts";

const errorCode = (body: unknown): string | undefined => {
  if (typeof body !== "object" || body === null) return undefined;
  const err = (body as { error?: unknown }).error;
  const code = typeof err === "object" && err !== null ? (err as { code?: unknown }).code : undefined;
  return typeof code === "string" ? code : undefined;
};

const byMap = (map: ErrorMap, reply: WireReply): ErrorType | null => {
  if (reply.status >= 200 && reply.status < 300) return null;
  const code = errorCode(reply.body);
  const rule = map.byCode.find((r) => r.status === reply.status);
  const coded = rule !== undefined && code !== undefined ? rule.codes[code] : undefined;
  if (coded !== undefined) return coded;
  const mapped = map.byStatus[reply.status];
  if (mapped !== undefined) return mapped;
  return reply.status >= 500 ? "provider_unavailable" : "invalid_request";
};

/** Retry-After as integer seconds -> ms. HTTP-date form is not parsed (TODO if a vendor documents it). */
const retryAfterMs = (map: ErrorMap, reply: WireReply): number | undefined => {
  if (!map.retryHeaders.includes("retry-after")) return undefined;
  const raw = header(reply.headers, "retry-after");
  const secs = raw === undefined ? NaN : Number(raw);
  return Number.isFinite(secs) && secs >= 0 ? secs * 1000 : undefined;
};

export const classifyReply = (reply: WireReply): ErrorType | null => byMap(GENERIC_ERRORS, reply);

export const classifyVendorReply = (d: Descriptor, reply: WireReply): { type: ErrorType | null; retryAfterMs: number | undefined } =>
  ({ type: byMap(d.errors, reply), retryAfterMs: retryAfterMs(d.errors, reply) });
