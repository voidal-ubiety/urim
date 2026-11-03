import { test } from "node:test";
import assert from "node:assert/strict";
import { lineDiff } from "../src/diff.ts";

test("identical text has no diff", () => assert.deepEqual(lineDiff("a\nb", "a\nb"), []));
test("changed line shows - then +", () => assert.deepEqual(lineDiff("a\nb\nc", "a\nB\nc"), ["- b", "+ B"]));
test("insert and delete", () => assert.deepEqual(lineDiff("a\nc", "a\nb\nc\nd"), ["+ b", "+ d"]));
test("from empty", () => assert.deepEqual(lineDiff("", "x"), ["- ", "+ x"]));
