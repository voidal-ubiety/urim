// C: lockfile read/write (design §6). Readers validate and ignore unknown keys; the writer is strict.
import { UrimError, type Issue } from "./errors.ts";
import { deepFreeze } from "./freeze.ts";
import { prettyCanonical } from "./pretty.ts";
import type { EvalProvenance, Lock } from "./types.ts";

export type LockParse = { ok: true; lock: Lock } | { ok: false; issues: readonly Issue[] };

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const isHash = (v: unknown): v is string => typeof v === "string" && v.startsWith("sha256:") && v.length > 7;

export const parseLock = (v: unknown): LockParse => {
  const issues: Issue[] = [];
  const bad = (path: string, message: string) => { issues.push({ path, message }); };
  if (!isObj(v)) return { ok: false, issues: [{ path: "$", message: "lock must be an object" }] };
  if (v["lock"] !== 1) bad("lock", "unsupported lock format (expected 1)");
  const c = v["contract"];
  if (!isObj(c) || typeof c["id"] !== "string" || !isHash(c["hash"])) bad("contract", "needs {id: string, hash: sha256:...}");
  const cuts = v["cuts"];
  if (!isObj(cuts)) bad("cuts", "must be an object");
  else for (const [name, perTier] of Object.entries(cuts)) {
    if (!isObj(perTier)) { bad(`cuts.${name}`, "must be an object"); continue; }
    for (const [t, n] of Object.entries(perTier)) {
      if (typeof n !== "number" || !(n >= 0 && n <= 1)) bad(`cuts.${name}.${t}`, "cutoff must be a number within 0..1");
    }
  }
  const tiers = v["tiers"];
  if (tiers !== undefined && (!Array.isArray(tiers) || !tiers.every((t) => isObj(t) && typeof t["id"] === "string"
    && (t["descriptorHash"] === null || isHash(t["descriptorHash"]))))) bad("tiers", "must be [{id, descriptorHash: sha256:...|null}]");
  const ev = v["eval"];
  if (ev !== undefined && !(isObj(ev) && isHash(ev["setHash"]) && Number.isInteger(ev["n"]) && (ev["n"] as number) >= 0
    && Number.isInteger(ev["repeat"]) && (ev["repeat"] as number) >= 1 && typeof ev["at"] === "string" && typeof ev["objectivesMet"] === "boolean")) {
    bad("eval", "must be {setHash, n >= 0, repeat >= 1, at, objectivesMet}");
  }
  if (issues.length > 0) return { ok: false, issues };
  const contract = c as { id: string; hash: string };
  const e = ev as EvalProvenance | undefined;
  return { ok: true, lock: deepFreeze({
    lock: 1 as const, contract: { id: contract.id, hash: contract.hash },
    ...(tiers === undefined ? {} : { tiers: (tiers as { id: string; descriptorHash: string | null }[]).map((t) => ({ id: t.id, descriptorHash: t.descriptorHash })) }),
    cuts: structuredClone(cuts) as Lock["cuts"],
    ...(e === undefined ? {} : { eval: { setHash: e.setHash, n: e.n, repeat: e.repeat, at: e.at, objectivesMet: e.objectivesMet } }),
  }) };
};

export const serializeLock = (lock: Lock): string => {
  const r = parseLock(lock);
  if (!r.ok) throw new UrimError("lock_violation", `refusing to write invalid lock: ${r.issues.map((i) => `${i.path}: ${i.message}`).join("; ")}`, { issues: r.issues });
  return prettyCanonical(r.lock);
};
