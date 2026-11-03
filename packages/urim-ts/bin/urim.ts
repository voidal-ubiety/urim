#!/usr/bin/env node
// A: binds the CLI to the real filesystem. No network.
import { mkdir, readFile, writeFile, access } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { main } from "../src/cli.ts";

const code = await main(process.argv.slice(2), {
  readText: (p) => readFile(p, "utf8"),
  writeText: async (p, t) => { await mkdir(dirname(p), { recursive: true }); await writeFile(p, t); },
  exists: (p) => access(p).then(() => true, () => false),
  importModule: (p) => import(pathToFileURL(resolve(p)).href) as Promise<Record<string, unknown>>,
  out: (l) => { process.stdout.write(`${l}\n`); }, err: (l) => { process.stderr.write(`${l}\n`); },
});
process.exitCode = code;
