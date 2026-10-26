// C-080, C-081, C-089: limits and file-type rules that need generated files, not fixtures.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, test } from "node:test";
import * as urim from "../dist/index.js";

const dir = mkdtempSync(join(tmpdir(), "urim-limits-"));
after(() => rmSync(dir, { recursive: true, force: true }));
const LOCK = "hoshen: 2\nurim: x\n";
/** A valid lockfile padded with a comment to exactly `size` bytes. */
const padded = (size) => `${LOCK}#${"x".repeat(size - LOCK.length - 2)}\n`;

test("C-080 MAX_BYTES and MAX_DEPTH are exported and match the contract", () => {
  assert.equal(urim.MAX_BYTES, 1_048_576);
  assert.equal(urim.MAX_DEPTH, 64);
});

test("C-080 a file of exactly MAX_BYTES is accepted; one byte more is too large", () => {
  const ok = join(dir, "max.lock");
  writeFileSync(ok, padded(urim.MAX_BYTES));
  assert.equal(urim.checkFile(ok).line, `${ok}: ok (lockfile, hoshen 2, urim x)`);
  const big = join(dir, "big.lock");
  writeFileSync(big, padded(urim.MAX_BYTES + 1));
  assert.equal(urim.checkFile(big).line, `${big}: error: file too large (max 1048576 bytes)`);
  assert.equal(
    urim.checkText("t", padded(urim.MAX_BYTES + 1)).line,
    "t: error: file too large (max 1048576 bytes)",
  );
  // Bytes, not UTF-16 code units: 2-byte characters count twice.
  assert.equal(
    urim.checkText("t", `${LOCK}#${"é".repeat(urim.MAX_BYTES / 2)}`).line,
    "t: error: file too large (max 1048576 bytes)",
  );
});

test("C-081 FIFOs and devices are refused without blocking; symlinks to files are followed", () => {
  const fifo = join(dir, "fifo");
  execFileSync("mkfifo", [fifo]);
  assert.equal(urim.checkFile(fifo).line, `${fifo}: error: not a regular file`);
  assert.equal(urim.checkFile("/dev/zero").line, "/dev/zero: error: not a regular file");
  assert.equal(urim.checkFile("/dev/null").line, "/dev/null: error: not a regular file");
  const target = join(dir, "target.lock");
  writeFileSync(target, LOCK);
  const link = join(dir, "link.lock");
  symlinkSync(target, link);
  assert.equal(urim.checkFile(link).line, `${link}: ok (lockfile, hoshen 2, urim x)`);
});

test("C-013 a read error after a successful open reports cannot read file", () => {
  // /proc/self/mem opens as a regular file but reading offset 0 fails with EIO.
  assert.equal(urim.checkFile("/proc/self/mem").line, "/proc/self/mem: error: cannot read file");
});

test("C-013 a NUL in the path reports cannot read file (bug B-3 parity)", () => {
  const result = urim.checkFile("a\0b");
  assert.deepEqual([result.ok, result.exitCode], [false, 1]);
  assert.equal(result.line, "a\\u{0000}b: error: cannot read file");
});

test("C-089 control and invisible characters in the file name are escaped", () => {
  assert.equal(
    urim.checkText("a\u001b[31mb\u202e\u0085", "[]").line,
    "a\\u{001B}[31mb\\u{202E}\\u{0085}: error: root must be a mapping",
  );
  assert.equal(urim.checkText("\ud800x", "[]").line, "\\u{D800}x: error: root must be a mapping");
  assert.equal(urim.checkText("\u{E0041}", "[]").line, "\\u{E0041}: error: root must be a mapping");
});

test("C-071 misuse of the API (non-string text) is a TypeError, not a check result", () => {
  assert.throws(() => urim.checkText("f", 42), TypeError);
});

test("C-080 a 300k-item flow sequence inside MAX_BYTES is checked, not a crash (bug B-8)", () => {
  const text = `hoshen: 2\nurim: x\nq: [${"1,".repeat(300_000)}1]\n`;
  assert.equal(urim.checkText("wide.lock", text).line, "wide.lock: ok (lockfile, hoshen 2, urim x)");
});
