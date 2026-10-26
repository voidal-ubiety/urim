// Reading a file safely: regular files only, bounded size, strict UTF-8 (same as read.rs/.py).
// The path is opened first (O_NONBLOCK, so a FIFO cannot hang the open) and the open handle is
// inspected, so there is no stat-then-open race. Size is enforced by reading at most one byte
// past the limit, not by trusting the reported size.
// Implements: C-010, C-011, C-012, C-013, C-080, C-081
import { closeSync, constants, fstatSync, openSync, readSync } from "node:fs";
import { MAX_BYTES } from "./limits.js";
import { Failure, Problem } from "./problem.js";

const openFlags = constants.O_RDONLY | constants.O_NONBLOCK;

export function readText(path: string): string {
  let fd: number;
  try {
    fd = openSync(path, openFlags);
  } catch {
    throw new Failure(Problem.cannotRead);
  }
  try {
    if (!fstatSync(fd).isFile()) throw new Failure(Problem.notRegularFile);
    const buf = Buffer.alloc(MAX_BYTES + 1);
    let len = 0;
    for (;;) {
      let n: number;
      try {
        n = readSync(fd, buf, len, buf.length - len, null);
      } catch {
        throw new Failure(Problem.cannotRead);
      }
      len += n;
      if (n === 0 || len === buf.length) break;
    }
    if (len > MAX_BYTES) throw new Failure(Problem.tooLarge);
    try {
      return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(buf.subarray(0, len));
    } catch {
      throw new Failure(Problem.notUtf8);
    }
  } finally {
    closeSync(fd);
  }
}
