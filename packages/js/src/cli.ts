#!/usr/bin/env node
import { checkFile } from "./check.js";
import { VERSION } from "./index.js";

const USAGE = "usage: urim check <file>";

/** Run the CLI on `args` (argv without node and the script); returns the process exit code. */
export function main(args: readonly string[]): number {
  if (args.length === 1 && (args[0] === "--version" || args[0] === "-V")) {
    console.log(`urim ${VERSION}`);
    return 0;
  }
  if (args.length === 1 && (args[0] === "--help" || args[0] === "-h")) {
    console.log(USAGE);
    return 0;
  }
  const [command, path, ...extra] = args;
  if (command !== "check" || path === undefined || extra.length > 0) {
    console.error(USAGE);
    return 2;
  }
  const result = checkFile(path);
  (result.ok ? console.log : console.error)(result.line);
  return result.exitCode;
}

process.exitCode = main(process.argv.slice(2));
