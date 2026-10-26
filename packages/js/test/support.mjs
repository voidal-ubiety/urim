// Shared helpers for the contract suite. Fixtures live in ../../../fixtures and are shared
// with the Python and Rust suites; see CONTRACT.md for the meaning of each ID.
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const FIXTURES = resolve(here, "../../../fixtures");
export const CLI = resolve(here, "../dist/cli.js");
export const PACKAGE_ROOT = resolve(here, "..");

const load = (name) => JSON.parse(readFileSync(resolve(FIXTURES, name), "utf8")).cases;
export const FILE_CASES = load("cases.json");
export const CLI_CASES = load("cli.json");
export const DIVERGENCES = load("divergences.json");

/** Group cases by contract ID, preserving file order. */
export function byId(cases) {
  const groups = new Map();
  for (const c of cases) {
    if (!groups.has(c.id)) groups.set(c.id, []);
    groups.get(c.id).push(c);
  }
  return groups;
}

/** Run the built CLI. `cwd` defaults to the fixtures directory. */
export function runCli(args, cwd = FIXTURES) {
  const r = spawnSync(process.execPath, [CLI, ...args], { cwd, encoding: "utf8" });
  return { exit: r.status, stdout: r.stdout, stderr: r.stderr };
}
