// D: the one error class and its closed type list (design §5.3, D11).
export type ErrorType =
  | "invalid_input" | "invalid_definition" | "lock_violation"
  | "auth" | "invalid_request" | "refused" | "limit_exceeded"
  | "timeout" | "provider_unavailable" | "rate_limited" | "quota_exceeded"
  | "nonconformant_response" | "budget"
  | "cancelled" | "all_tiers_failed" | "internal";

/** Types that `failover.on` may list. Everything else always abstains. */
export const FAILOVER_TYPES: ReadonlySet<ErrorType> = new Set<ErrorType>([
  "timeout", "provider_unavailable", "rate_limited", "quota_exceeded", "nonconformant_response", "budget",
]);

export type Issue = { readonly path: string; readonly message: string };

type Details = {
  readonly cause?: unknown; readonly tier?: string; readonly status?: number;
  readonly requestId?: string; readonly retryAfterMs?: number; readonly issues?: readonly Issue[];
};

export class UrimError extends Error {
  readonly type: ErrorType;
  readonly retryable: boolean;
  readonly tier: string | undefined;
  readonly status: number | undefined;
  readonly requestId: string | undefined;
  /** From Retry-After when the vendor sent one; Urim never sleeps on it, it is information for the caller. */
  readonly retryAfterMs: number | undefined;
  readonly issues: readonly Issue[] | undefined;

  constructor(type: ErrorType, message: string, details: Details = {}) {
    super(message, details.cause === undefined ? undefined : { cause: details.cause });
    this.name = "UrimError";
    this.type = type;
    this.retryable = FAILOVER_TYPES.has(type);
    this.tier = details.tier;
    this.status = details.status;
    this.requestId = details.requestId;
    this.retryAfterMs = details.retryAfterMs;
    this.issues = details.issues === undefined ? undefined : Object.freeze([...details.issues]);
    Object.freeze(this);
  }
}

export const invalidDefinition = (issues: readonly Issue[]): UrimError =>
  new UrimError("invalid_definition", issues.map((i) => `${i.path}: ${i.message}`).join("; "), { issues });
