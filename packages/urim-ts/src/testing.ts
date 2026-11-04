// A (test double): implements the adapter barrier from a script. Imported from "@voidal-ubiety/urim/testing" later.
import { UrimError, type ErrorType } from "./errors.ts";
import type { WireReply, WireRequest } from "./types.ts";

export type Adapter = {
  /** Provider id this adapter serves (matches Tier.provider); "*" serves any tier (test doubles only). */
  readonly provider: string;
  /** Env var NAME holding the credential; the value is looked up at send time and never logged. */
  readonly credentialEnv?: string;
  send(req: WireRequest, io: { signal: AbortSignal; fetch: typeof fetch; credential: string }): Promise<WireReply>;
};
export type FakeStep = { fail: ErrorType } | { body: unknown; status?: number } | { hang: true };
export type FakeProvider = Adapter & { readonly calls: readonly WireRequest[] };

/** `cycle: true` replays each tier's steps round-robin (eval sets, `fit --repeat`). Keys starting with "_" are ignored. */
export const fakeProvider = (script: Readonly<Record<string, readonly FakeStep[]>>, opts: { readonly cycle?: boolean } = {}): FakeProvider => {
  const cursor = new Map<string, number>();
  const calls: WireRequest[] = [];
  return {
    provider: "*",
    calls,
    async send(req, io) {
      if (io.signal.aborted) throw new UrimError("cancelled", "aborted before send", { tier: req.tierId });
      calls.push(req);
      const index = cursor.get(req.tierId) ?? 0;
      const steps = script[req.tierId];
      const step = steps?.[opts.cycle === true && steps.length > 0 ? index % steps.length : index];
      if (step === undefined) throw new Error(`fakeProvider: no scripted step ${index} for ${req.tierId}`); // test bug, fail fast
      cursor.set(req.tierId, index + 1);
      if ("hang" in step) return new Promise<never>(() => undefined); // only an abort or deadline ends it
      if ("fail" in step) throw new UrimError(step.fail, `scripted ${step.fail}`, { tier: req.tierId });
      return { status: step.status ?? 200, headers: {}, body: step.body, latencyMs: 0 };
    },
  };
};
