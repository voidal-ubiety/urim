// A (thin): `urim` CLI. All I/O goes through the injected CliIo so every command is testable in memory.
// No network code: emit/providers are pure transforms; fit runs only with --fake adapters in this slice.
import { lineDiff } from "./diff.ts";
import { emit } from "./emit.ts";
import { parseCases, runFit } from "./fit.ts";
import { serializeLock } from "./lock.ts";
import { prettyCanonical } from "./pretty.ts";
import { generateProviders, parseRegistry } from "./providers.ts";
import { fakeProvider, type FakeStep } from "./testing.ts";
import type { Definition, PriceTable } from "./types.ts";

export type CliIo = {
  readText(path: string): Promise<string>; writeText(path: string, text: string): Promise<void>;
  exists(path: string): Promise<boolean>; importModule(path: string): Promise<Record<string, unknown>>;
  out(line: string): void; err(line: string): void;
  /** Clock for `fit` (latency and the lock's eval.at); defaults to Date.now. Injected for reproducible vectors. */
  now?: () => number;
};

const USAGE = [
  "usage:",
  "  urim emit <module...> --out <dir>",
  "  urim fit <module> --cases <eval.jsonl> --fake <fake.json> --lock <out> [--prices <prices.json>] [--export <name>] [--yes] [--repeat N] [--report]",
  "  urim providers --registry <registry.json> --out <file.ts>",
];

const HELP = new Set(["--help", "-h", "help"]);

type Parsed = { positional: string[]; flags: Record<string, string | true> };
const parseArgs = (argv: readonly string[]): Parsed => {
  const positional: string[] = []; const flags: Record<string, string | true> = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]!;
    if (!a.startsWith("--")) { positional.push(a); continue; }
    const next = argv[i + 1];
    if (["--yes", "--report"].includes(a) || next === undefined || next.startsWith("--")) flags[a.slice(2)] = true;
    else { flags[a.slice(2)] = next; i++; }
  }
  return { positional, flags };
};
const str = (p: Parsed, k: string): string | undefined => (typeof p.flags[k] === "string" ? p.flags[k] as string : undefined);

export const isDefinition = (v: unknown): v is Definition => {
  const d = v as Partial<Definition> | null;
  return typeof d === "object" && d !== null && typeof d.contract === "string" && Array.isArray(d.tiers)
    && typeof d.questions === "object" && typeof d.input?.parse === "function";
};
const slug = (contract: string) => contract.replace(/[^A-Za-z0-9._-]/g, "_");

const emitCmd = async (p: Parsed, io: CliIo): Promise<number> => {
  const out = str(p, "out");
  if (out === undefined || p.positional.length === 0) { USAGE.forEach(io.err); return 1; }
  const hashes: Record<string, string> = {};
  for (const path of p.positional) {
    const defs = Object.values(await io.importModule(path)).filter(isDefinition);
    if (defs.length === 0) { io.err(`${path}: no decision definitions exported`); return 1; }
    for (const def of defs) {
      const e = emit(def);
      const file = `${out}/${slug(def.contract)}.contract.json`;
      const text = prettyCanonical(e.document);
      const before = (await io.exists(file)) ? await io.readText(file) : null;
      if (before === text) io.out(`unchanged ${file} ${e.hash}`);
      else {
        if (before !== null) { io.out(`changed ${file}`); lineDiff(before, text).forEach(io.out); }
        await io.writeText(file, text);
        io.out(`wrote ${file} ${e.hash}`);
      }
      hashes[def.contract] = e.hash;
    }
  }
  await io.writeText(`${out}/urim.hashes.json`, prettyCanonical(hashes));
  return 0;
};

const fitCmd = async (p: Parsed, io: CliIo): Promise<number> => {
  const [modPath] = p.positional; const casesPath = str(p, "cases"); const lockPath = str(p, "lock"); const fakePath = str(p, "fake");
  if (modPath === undefined || casesPath === undefined || lockPath === undefined) { USAGE.forEach(io.err); return 1; }
  if (fakePath === undefined) { io.err("fit: real provider adapters are not in this build; pass --fake <fake.json>"); return 1; }
  const mod = await io.importModule(modPath);
  const name = str(p, "export");
  const def = name === undefined ? Object.values(mod).find(isDefinition) : mod[name];
  if (!isDefinition(def)) { io.err(`fit: no decision definition in ${modPath}`); return 1; }
  const repeat = Number(str(p, "repeat") ?? "1");
  if (!Number.isInteger(repeat) || repeat < 1) { io.err("fit: --repeat must be a positive integer"); return 1; }
  const pricesPath = str(p, "prices");
  const prices = pricesPath === undefined ? undefined : JSON.parse(await io.readText(pricesPath)) as PriceTable;
  const script = JSON.parse(await io.readText(fakePath)) as Record<string, FakeStep[]>;
  const cases = parseCases(await io.readText(casesPath));
  const r = await runFit({ def, cases, adapters: [fakeProvider(script, { cycle: true })], ...(prices === undefined ? {} : { prices }), repeat, yes: p.flags["yes"] === true, ...(io.now === undefined ? {} : { now: io.now }) });
  const e = r.estimate;
  io.out(`cost estimate: ${e.total === null ? "incomplete" : `${e.total} ${e.currency}`} for ${cases.length} cases x ${repeat} run(s) x ${def.tiers.length} tier(s)`);
  for (const [t, v] of Object.entries(e.perTier)) io.out(`  ${t}: ${v} ${e.currency}`);
  for (const t of e.unknown) io.out(`  unknown price: ${t} (not estimated)`);
  if (r.status === "needs_confirmation") { io.out("refusing to call providers without --yes"); return 2; }
  if (p.flags["report"] === true) io.out(JSON.stringify(r.report));
  if (r.status === "objectives_unmet") { io.err(`fit: objectives unmet: ${r.unmet.join(", ")}; lock not written`); return 1; }
  await io.writeText(lockPath, serializeLock(r.lock));
  io.out(`wrote ${lockPath}`);
  return 0;
};

const providersCmd = async (p: Parsed, io: CliIo): Promise<number> => {
  const reg = str(p, "registry"); const out = str(p, "out");
  if (reg === undefined || out === undefined) { USAGE.forEach(io.err); return 1; }
  const registry = parseRegistry(JSON.parse(await io.readText(reg)));
  await io.writeText(out, generateProviders(registry, { source: reg, ...(str(p, "import") === undefined ? {} : { importFrom: str(p, "import")! }) }));
  io.out(`wrote ${out}${registry.example ? " (EXAMPLE DATA)" : ""}`);
  return 0;
};

export const main = async (argv: readonly string[], io: CliIo): Promise<number> => {
  const [cmd, ...rest] = argv;
  if ((cmd !== undefined && HELP.has(cmd)) || rest.some((a) => a === "--help" || a === "-h")) { USAGE.forEach(io.out); return 0; }
  const p = parseArgs(rest);
  try {
    if (cmd === "emit") return await emitCmd(p, io);
    if (cmd === "fit") return await fitCmd(p, io);
    if (cmd === "providers") return await providersCmd(p, io);
  } catch (e) {
    io.err(`urim ${cmd}: ${e instanceof Error ? e.message : String(e)}`);
    return 1;
  }
  USAGE.forEach(io.err);
  return 1;
};
