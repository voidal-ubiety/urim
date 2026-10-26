#!/usr/bin/env bash
# Run all three `urim` CLIs over every shared case and require byte-identical stdout,
# stderr, and exit codes:
#   - fixtures/cases.json: `urim check fixtures/<path>` from the repo root;
#   - fixtures/cli.json:   each case's argv, run with cwd = fixtures/.
# fixtures/divergences.json is deliberately NOT checked here (see CONTRACT.md, section D).
# Build first: (cd packages/js && npm ci && npm run build); (cd packages/rust && cargo build);
# and install packages/python into the interpreter named by $PYTHON (default python3).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=${PYTHON:-python3}
JS=(node "$ROOT/packages/js/dist/cli.js")
RS=("$ROOT/packages/rust/target/debug/urim")
PYC=("$PY" -m urim)
err=$(mktemp); recs=$(mktemp); trap 'rm -f "$err" "$recs"' EXIT
fail=0; n=0

# Emit "<cwd>\0<argc>\0<arg>\0..." records for every invocation.
records() {
  "$PY" - <<'PYEOF'
import json, sys
out = sys.stdout
for c in json.load(open("fixtures/cases.json"))["cases"]:
    args = ["check", "fixtures/" + c["path"]]
    out.write("\0".join([".", str(len(args)), *args]) + "\0")
for c in json.load(open("fixtures/cli.json"))["cases"]:
    out.write("\0".join(["fixtures", str(len(c["args"])), *c["args"]]) + "\0")
PYEOF
}

# Write the records to a file first: a failure inside `< <(records)` would not stop the script,
# so a broken $PYTHON used to give "parity OK: 0 invocations" (bug B-7).
records >"$recs"

while IFS= read -r -d '' cwd; do
  IFS= read -r -d '' argc
  args=()
  for ((i = 0; i < argc; i++)); do IFS= read -r -d '' a; args+=("$a"); done
  n=$((n + 1)); ref=""
  for impl in JS RS PYC; do
    declare -n cmd=$impl
    out=$(cd "$cwd" && "${cmd[@]}" "${args[@]}" 2>"$err") && code=0 || code=$?
    got="exit=$code|out=$out|err=$(cat "$err")"
    if [[ -z "$ref" ]]; then ref=$got; elif [[ "$got" != "$ref" ]]; then
      echo "MISMATCH [$impl] (cwd $cwd) ${args[*]}"; echo "  ref: $ref"; echo "  got: $got"; fail=1
    fi
  done
done <"$recs"
[[ $n -gt 0 ]] || { echo "parity: no invocations found" >&2; exit 1; }
[[ $fail -eq 0 ]] && echo "parity OK: $n invocations x 3 implementations identical" || exit 1
