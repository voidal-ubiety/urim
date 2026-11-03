import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { main, type CliIo } from "../src/cli.ts";
import { emit } from "../src/index.ts";
import { triage } from "./fixtures.ts";
import { gate } from "./fixtures/fit.decision.ts";

const memIo = (files: Record<string, string> = {}, modules: Record<string, Record<string, unknown>> = {}) => {
  const out: string[] = []; const err: string[] = [];
  const io: CliIo = {
    readText: async (p) => { const v = files[p]; if (v === undefined) throw new Error(`ENOENT ${p}`); return v; },
    writeText: async (p, t) => { files[p] = t; },
    exists: async (p) => p in files,
    importModule: async (p) => { const m = modules[p]; if (m === undefined) throw new Error(`no module ${p}`); return m; },
    out: (l) => out.push(l), err: (l) => err.push(l),
  };
  return { io, files, out, err };
};
const fx = (name: string) => readFileSync(new URL(`./fixtures/${name}`, import.meta.url), "utf8");

test("emit writes canonical contract + hash index for each definition export", async () => {
  const m = memIo({}, { "d.ts": { triage, notADecision: { x: 1 } } });
  assert.equal(await main(["emit", "d.ts", "--out", "out"], m.io), 0);
  const written = m.files["out/incident-triage_2.0.0.contract.json"]!;
  assert.deepEqual(JSON.parse(written), JSON.parse(emit(triage).json));
  assert.deepEqual(JSON.parse(m.files["out/urim.hashes.json"]!), { [triage.contract]: emit(triage).hash });
});
test("emit again with no change prints unchanged and no diff", async () => {
  const m = memIo({}, { "d.ts": { triage } });
  await main(["emit", "d.ts", "--out", "o"], m.io);
  m.out.length = 0;
  await main(["emit", "d.ts", "--out", "o"], m.io);
  assert.ok(m.out.some((l) => /unchanged/.test(l)) && !m.out.some((l) => l.startsWith("+ ")));
});
test("emit prints a diff when output changes", async () => {
  const m = memIo({}, { "d.ts": { triage } });
  await main(["emit", "d.ts", "--out", "o"], m.io);
  m.files["o/incident-triage_2.0.0.contract.json"] = m.files["o/incident-triage_2.0.0.contract.json"]!.replace("\"typesafe_normalized\"", "\"top_probability\"");
  m.out.length = 0;
  await main(["emit", "d.ts", "--out", "o"], m.io);
  assert.ok(m.out.some((l) => l.includes('"noul": "top_probability"') && l.startsWith('-')) && m.out.some((l) => l.includes('"noul": "typesafe_normalized"') && l.startsWith('+')), m.out.join('\n'));
});
test("emit with no definitions in a module fails", async () => {
  const m = memIo({}, { "d.ts": { x: 1 } });
  assert.equal(await main(["emit", "d.ts", "--out", "o"], m.io), 1);
});

const fitFiles = () => ({ "cases.jsonl": fx("eval.fit.jsonl"), "fake.json": fx("fake.fit.json"),
  "prices.json": JSON.stringify({ id: "p", asOf: "2026-10-28", url: "https://example.invalid/PLACEHOLDER",
    entries: { "typesafe/jev@1.14.0": { perCall: 0.004, currency: "USD" } } }) });
const fitArgs = ["fit", "f.ts", "--cases", "cases.jsonl", "--fake", "fake.json", "--prices", "prices.json", "--lock", "urim.lock.json"];

test("fit without --yes shows the estimate, exits 2, writes nothing", async () => {
  const m = memIo(fitFiles(), { "f.ts": { gate } });
  assert.equal(await main(fitArgs, m.io), 2);
  assert.ok(m.out.some((l) => /estimate/i.test(l)) && m.out.some((l) => /unknown price.*clef/i.test(l)));
  assert.ok(!("urim.lock.json" in m.files));
});
test("fit --yes writes a valid lock", async () => {
  const m = memIo(fitFiles(), { "f.ts": { gate } });
  assert.equal(await main([...fitArgs, "--yes"], m.io), 0);
  const lock = JSON.parse(m.files["urim.lock.json"]!) as { contract: { hash: string }; cuts: unknown };
  assert.equal(lock.contract.hash, emit(gate).hash);
});
test("fit --repeat 2 --report prints a JSON report", async () => {
  const m = memIo(fitFiles(), { "f.ts": { gate } });
  assert.equal(await main([...fitArgs, "--yes", "--repeat", "2", "--report"], m.io), 0);
  const report = JSON.parse(m.out.find((l) => l.startsWith("{"))!) as { repeat: number };
  assert.equal(report.repeat, 2);
});
test("fit without --fake refuses: no real adapters in this build", async () => {
  const m = memIo(fitFiles(), { "f.ts": { gate } });
  assert.equal(await main(["fit", "f.ts", "--cases", "cases.jsonl", "--lock", "l", "--yes"], m.io), 1);
  assert.ok(m.err.some((l) => /--fake/.test(l)));
});
test("providers command regenerates constants from a registry", async () => {
  const m = memIo({ "r.json": fx("registry.example.json") });
  assert.equal(await main(["providers", "--registry", "r.json", "--out", "p.ts"], m.io), 0);
  assert.match(m.files["p.ts"]!, /Jev_1_14_0/);
});
test("unknown command prints usage and exits 1", async () => assert.equal(await main(["nope"], memIo().io), 1));

test("bin smoke: real fs emit into a temp dir", () => {
  const dir = mkdtempSync(join(tmpdir(), "urim-emit-"));
  const bin = new URL("../bin/urim.ts", import.meta.url).pathname;
  const mod = new URL("./fixtures.ts", import.meta.url).pathname;
  const r = spawnSync(process.execPath, [bin, "emit", mod, "--out", dir], { encoding: "utf8" });
  assert.equal(r.status, 0, r.stderr);
  assert.ok(existsSync(join(dir, "incident-triage_2.0.0.contract.json")));
});

test("bin: --help and -h print usage to stdout and exit 0 (matches urim-py)", () => {
  const bin = new URL("../bin/urim.ts", import.meta.url).pathname;
  for (const flag of ["--help", "-h"]) {
    const r = spawnSync(process.execPath, [bin, flag], { encoding: "utf8" });
    assert.equal(r.status, 0, r.stderr);
    assert.match(r.stdout, /^usage:\n {2}urim emit /);
    assert.equal(r.stderr, "");
  }
});
