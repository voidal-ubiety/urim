"""C: minimal LCS line diff for ``urim emit`` change reports, mirroring urim-ts src/diff.ts.

Only changed lines are returned (``- old``, ``+ new``)."""

from __future__ import annotations


def line_diff(before: str, after: str) -> list[str]:
    if before == after:
        return []
    a, b = before.split("\n"), after.split("\n")
    lcs = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            lcs[i][j] = lcs[i + 1][j + 1] + 1 if a[i] == b[j] else max(lcs[i + 1][j], lcs[i][j + 1])
    out: list[str] = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i, j = i + 1, j + 1
        elif lcs[i + 1][j] >= lcs[i][j + 1]:
            out.append(f"- {a[i]}")
            i += 1
        else:
            out.append(f"+ {b[j]}")
            j += 1
    out += [f"- {x}" for x in a[i:]] + [f"+ {x}" for x in b[j:]]
    return out
