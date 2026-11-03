// A: the edge. createClient binds adapters/env/clock/hooks; decide is the one thin I/O loop over the pure plan.
// Everything it decides is delegated to calculations: planAttempts, nextStep, encode/decode, resolveCuts, buildEnvelope.
import { encodeRequest, decodeReply, requestIdOf, type TokenUsage } from "./camps/index.ts";
import { emit } from "./emit.ts";
import { buildEnvelope } from "./envelope.ts";
import { UrimError, type ErrorType } from "./errors.ts";
import { nextStep, planAttempts } from "./plan.ts";
import { resolveCuts } from "./cuts.ts";
import { deepFreeze } from "./freeze.ts";
import type { Adapter } from "./testing.ts";
import type {
  Answers, Attempt, CutsOf, Budget, Definition, Envelope, Failure, Lock, Plan, PriceTable, Questions, Result, Settled, Success, Thresholds, Tier, WireReply,
} from "./types.ts";

export type ClientDeps = {
  readonly adapters: readonly Adapter[];
  readonly env?: Readonly<Record<string, string | undefined>>;
  readonly mode?: "dev" | "prod";
  /** Decisions this client serves. Required for prod startup checks (D4/D6). */
  readonly decisions?: readonly Definition<any, any, any, any>[];
  readonly locks?: readonly Lock[];
  readonly prices?: PriceTable;
  readonly budget?: Budget;
  /** Default total deadline across all tiers, in ms (finite, > 0). Unset: no deadline. A call's deadlineMs overrides it. */
  readonly deadlineMs?: number;
  readonly raw?: boolean;
  readonly now?: () => number;
  readonly fetch?: typeof fetch;
  /** D3: fires once for every settled call (ok, interpret_failed, abstain) with a frozen Settled record. */
  readonly onSettled?: (settled: Settled) => void | Promise<void>;
  readonly onHookError?: (error: unknown, settled: Settled) => void;
};

export type DecideOptions = {
  /** deadlineMs: omitted/undefined uses the client default; null means no deadline for this call. */
  readonly signal?: AbortSignal; readonly deadlineMs?: number | null; readonly raw?: boolean; readonly budget?: Budget;
};

export type Client = {
  decide<I, Q extends Questions, Th extends Thresholds, T>(def: Definition<I, Q, Th, T>, input: I, opts?: DecideOptions): Promise<Result<T, CutsOf<Th>>>;
  decideOrThrow<I, Q extends Questions, Th extends Thresholds, T>(def: Definition<I, Q, Th, T>, input: I, opts?: DecideOptions): Promise<Success<T, CutsOf<Th>>>;
  explain(def: Definition<any, any, any, any>, opts?: Pick<DecideOptions, "budget" | "deadlineMs"> & { readonly input?: unknown }): Plan;
  flush(): Promise<void>;
};

// ---- startup checks (C) ----

const missingCuts = (def: Definition, lock: Lock): string[] =>
  Object.entries(def.thresholds).flatMap(([name, t]) => def.tiers
    .filter((tier) => lock.cuts[name]?.[tier.id] === undefined && t.default === null)
    .map((tier) => `${name}@${tier.id}`));

const prodProblems = (def: Definition, lock: Lock | undefined): string[] => {
  if (lock === undefined) return [`${def.contract}: no lock`];
  const hash = emit(def).hash;
  if (lock.contract.hash !== hash) return [`${def.contract}: lock hash ${lock.contract.hash} != emitted ${hash}`];
  return missingCuts(def, lock).map((m) => `${def.contract}: no cutoff for ${m}`);
};

/** Fix 2: every tier of a registered decision needs an adapter (exact provider or the "*" test double). */
export const missingAdapters = (def: Definition, adapters: readonly Adapter[]): string[] =>
  adapters.some((a) => a.provider === "*") ? [] : def.tiers
    .filter((t) => !adapters.some((a) => a.provider === t.provider))
    .map((t) => `${def.contract}: no adapter for provider ${t.provider} (tier ${t.id})`);

const contractHash = (def: Definition): string | null => { try { return emit(def).hash; } catch { return null; } };

/** C: build the uniform settled record. */
export const settledRecord = (def: Definition, outcome: Settled["outcome"], envelope: Envelope | null,
  error: UrimError | null, attempts: readonly Attempt[], at: string): Settled => deepFreeze({
  settled: "urim/1" as const, outcome,
  contract: { id: def.contract, hash: envelope?.contract.hash ?? contractHash(def) },
  envelope, attempts: [...attempts], at,
  error: error === null ? null : { type: error.type, message: error.message, tier: error.tier ?? null },
});

const lockFor = (locks: readonly Lock[] | undefined, def: Definition): Lock | undefined =>
  locks?.find((l) => l.contract.id === def.contract);

// ---- one attempt (A): send with abort + deadline; every outcome becomes data ----

// deadlineSpent: this attempt ended because the deadline timer fired (not because an adapter reported a timeout).
type AttemptResult = { ok: true; reply: WireReply } | { ok: false; error: UrimError; deadlineSpent?: true };

const sendOnce = async (adapter: Adapter, tier: Tier, req: ReturnType<typeof encodeRequest>, credential: string,
  fetchFn: typeof fetch, signal: AbortSignal | undefined, remainingMs: number | undefined): Promise<AttemptResult> => {
  if (remainingMs !== undefined && remainingMs <= 0) {
    return { ok: false, error: new UrimError("timeout", `deadline exhausted before ${tier.id}`, { tier: tier.id }), deadlineSpent: true };
  }
  const ctl = new AbortController();
  let reason: "cancelled" | "timeout" | undefined;
  const abort = (why: "cancelled" | "timeout") => { reason ??= why; ctl.abort(); };
  const onCaller = () => abort("cancelled");
  signal?.addEventListener("abort", onCaller, { once: true });
  const timer = remainingMs === undefined ? undefined : setTimeout(() => abort("timeout"), remainingMs);
  const aborted = new Promise<never>((_, reject) => ctl.signal.addEventListener("abort", () => reject(ctl.signal.reason), { once: true }));
  try {
    const reply = await Promise.race([adapter.send(req, { signal: ctl.signal, fetch: fetchFn, credential }), aborted]);
    return { ok: true, reply };
  } catch (cause) {
    if (reason !== undefined) {
      const error = new UrimError(reason, `${reason} during ${tier.id}`, { tier: tier.id, cause });
      return reason === "timeout" ? { ok: false, error, deadlineSpent: true } : { ok: false, error };
    }
    if (cause instanceof UrimError) return { ok: false, error: cause };
    return { ok: false, error: new UrimError("internal", `adapter threw for ${tier.id}`, { tier: tier.id, cause }) };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onCaller);
  }
};

const failure = (error: UrimError, attempts: readonly Attempt[]): Failure => Object.freeze({ ok: false, error, attempts: Object.freeze([...attempts]) });

export const createClient = (deps: ClientDeps): Client => {
  const mode = deps.mode ?? "dev";
  const now = deps.now ?? Date.now;
  const registered = new Set<Definition>(deps.decisions ?? []);
  if (deps.deadlineMs !== undefined && !(typeof deps.deadlineMs === "number" && Number.isFinite(deps.deadlineMs) && deps.deadlineMs > 0)) {
    throw new UrimError("invalid_definition", `deadlineMs must be a finite number > 0, got ${String(deps.deadlineMs)}`);
  }
  const deadlineFor = (o: { readonly deadlineMs?: number | null }): number | undefined =>
    o.deadlineMs === undefined ? deps.deadlineMs : o.deadlineMs ?? undefined;
  if (mode === "prod") {
    const problems = [...registered].flatMap((d) => prodProblems(d, lockFor(deps.locks, d)));
    if (problems.length > 0) throw new UrimError("lock_violation", problems.join("; "));
    const unrouted = [...registered].flatMap((d) => missingAdapters(d, deps.adapters));
    if (unrouted.length > 0) throw new UrimError("invalid_definition", unrouted.join("; "));
  }

  // Hook timeline (D3): fire-and-forget on a frozen envelope; errors isolated; flush() is the join point.
  const pending = new Set<Promise<void>>();
  let warned = false;
  const hookError = deps.onHookError ?? ((err: unknown) => {
    if (!warned) { warned = true; console.warn("urim: onSettled failed:", err instanceof Error ? err.message : String(err)); }
  });
  const settle = (record: Settled): void => {
    const hook = deps.onSettled;
    if (hook === undefined) return;
    const p: Promise<void> = Promise.resolve()
      .then(() => hook(record))
      .catch((err: unknown) => { try { hookError(err, record); } catch { /* the error sink must not throw into us */ } })
      .finally(() => { pending.delete(p); });
    pending.add(p);
  };

  const adapterFor = (tier: Tier): Adapter | undefined =>
    deps.adapters.find((a) => a.provider === tier.provider) ?? deps.adapters.find((a) => a.provider === "*");

  const decide = async <I, Q extends Questions, Th extends Thresholds, T>(
    defIn: Definition<I, Q, Th, T>, input: I, opts: DecideOptions = {}): Promise<Result<T, CutsOf<Th>>> => {
    const def = defIn as unknown as Definition;
    const started = now();
    const at = new Date(started).toISOString();
    const fail = (error: UrimError, attempts: readonly Attempt[]): Failure => {
      settle(settledRecord(def, "abstain", null, error, attempts, at));
      return failure(error, attempts);
    };
    if (mode === "prod" && !registered.has(def)) {
      return fail(new UrimError("lock_violation", `${def.contract} was not checked at startup (pass it in decisions)`), []);
    }
    const parsed = def.input.parse(input);
    if (!parsed.ok) return fail(new UrimError("invalid_input", "input does not match the schema", { issues: parsed.issues }), []);
    const prepared = def.prepare === undefined ? parsed.value : def.prepare(parsed.value);
    const budget = opts.budget ?? deps.budget;
    const plan = planAttempts(def, { input: prepared, ...(budget === undefined ? {} : { budget }), ...(deps.prices === undefined ? {} : { prices: deps.prices }) });

    const attempts: Attempt[] = [];
    let answered: { tier: Tier; answers: Answers; reply: WireReply; usage: TokenUsage | null } | undefined;
    const requestIds: Record<string, string> = {};
    let lastError: UrimError | undefined;
    // Once the deadline timer fires the deadline is spent, whatever the clock reads (a timer can fire a little
    // before now() reaches the deadline). Later tiers then fail as timeout without a call, as when remaining <= 0.
    let deadlineSpent = false;
    const deadlineMs = deadlineFor(opts);
    for (const step of plan.steps) {
      if (opts.signal?.aborted === true) return fail(new UrimError("cancelled", "aborted"), attempts);
      if (step.action === "skip") { attempts.push({ tier: step.tier.id, outcome: "skipped_budget", latencyMs: 0 }); continue; }
      const adapter = adapterFor(step.tier);
      if (adapter === undefined) return fail(new UrimError("invalid_definition", `no adapter for provider ${step.tier.provider}`, { tier: step.tier.id }), attempts);
      const t0 = now();
      const remaining = deadlineMs === undefined ? undefined : deadlineSpent ? 0 : deadlineMs - (t0 - started);
      const credential = adapter.credentialEnv === undefined ? "" : deps.env?.[adapter.credentialEnv] ?? "";
      const sent = await sendOnce(adapter, step.tier, encodeRequest(def, step.tier, prepared), credential,
        deps.fetch ?? globalThis.fetch, opts.signal, remaining);
      if (!sent.ok && sent.deadlineSpent === true) deadlineSpent = true;
      const decoded = sent.ok ? decodeReply(def, step.tier, sent.reply) : sent;
      const latencyMs = now() - t0;
      const rid = sent.ok ? requestIdOf(step.tier, sent.reply) : undefined;
      if (rid !== undefined) requestIds[step.tier.id] = rid;
      if (decoded.ok && sent.ok) {
        attempts.push({ tier: step.tier.id, outcome: "ok", latencyMs });
        answered = { tier: step.tier, answers: decoded.answers, reply: sent.reply, usage: decoded.usage };
        break;
      }
      const error = (decoded as { error: UrimError }).error;
      attempts.push({ tier: step.tier.id, outcome: error.type, latencyMs });
      if (nextStep(def, error.type as ErrorType) === "abstain") return fail(error, attempts);
      lastError = error;
    }
    if (answered === undefined) {
      return fail(new UrimError("all_tiers_failed", `every tier failed or was skipped for ${def.contract}`, { cause: lastError }), attempts);
    }

    const lock = lockFor(deps.locks, def);
    const cuts = resolveCuts(def, answered.tier, answered.answers, { mode, ...(lock === undefined ? {} : { lock }) });
    const wantRaw = opts.raw ?? deps.raw ?? false;
    const envelopeFor = (interpretFailed: boolean): Envelope => buildEnvelope({
      def, contractHash: emit(def).hash, tier: answered.tier, answers: answered.answers, cuts, attempts,
      requestIds, at,
      ...(answered.usage === null ? {} : { providerUsage: { ...answered.usage, cost: null } }),
      ...(deps.prices === undefined ? {} : { prices: deps.prices }),
      ...(wantRaw ? { raw: answered.reply.body } : {}),
      interpretFailed,
    });

    let value: unknown;
    try {
      value = def.interpret === undefined ? answered.answers : def.interpret({ answers: answered.answers, cut: cuts });
    } catch (defect) {
      settle(settledRecord(def, "interpret_failed", envelopeFor(true), null, attempts, at)); // D11: telemetry still sees it; the caller gets the original error, no fallback
      throw defect;
    }
    const envelope = envelopeFor(false);
    settle(settledRecord(def, "ok", envelope, null, attempts, at));
    return Object.freeze({ ok: true, value: value as T, envelope, fallback: envelope.fallback, thresholds: cuts as CutsOf<Th> });
  };

  return {
    decide,
    async decideOrThrow(def, input, opts) {
      const r = await decide(def, input, opts);
      if (!r.ok) throw r.error;
      return r;
    },
    explain: (def, opts = {}) => {
      const budget = opts.budget ?? deps.budget;
      const input = opts.input === undefined ? undefined : def.input.parse(opts.input);
      const prepared = input?.ok === true ? (def.prepare === undefined ? input.value : def.prepare(input.value)) : undefined;
      const plan = planAttempts(def, { ...(prepared === undefined ? {} : { input: prepared }),
        ...(budget === undefined ? {} : { budget }), ...(deps.prices === undefined ? {} : { prices: deps.prices }) });
      const deadlineMs = deadlineFor(opts);
      return deadlineMs === undefined ? plan : { ...plan, deadlineMs };
    },
    async flush() { while (pending.size > 0) await Promise.allSettled([...pending]); },
  };
};
