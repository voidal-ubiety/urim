#!/usr/bin/env node
import { checkFile } from "./check.js";
import { VERSION } from "./index.js";

const USAGE = "usage: urim check <file>";

export function main(args: string[]): number {
  if (args.length === 1 && (args[0] === "--version" || args[0] === "-V")) {
    console.log(`urim ${VERSION}`);
    return 0;
  }
  if (args.length === 1 && (args[0] === "--help" || args[0] === "-h")) {
    console.log(USAGE);
    return 0;
  }
  if (args.length !== 2 || args[0] !== "check") {
    console.error(USAGE);
    return 2;
  }
  const result = checkFile(args[1]);
  (result.ok ? console.log : console.error)(result.line);
  return result.exitCode;
}

process.exitCode = main(process.argv.slice(2));
