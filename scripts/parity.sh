#!/usr/bin/env bash
# Run all three `urim` CLIs over every shared fixture and require byte-identical
# stdout, stderr, and exit codes. Run from the repo root after building:
#   (cd packages/js && npm ci && npm run build)
#   (cd packages/rust && cargo build)
#   python -m pip install -e packages/python
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
JS=(node packages/js/dist/cli.js)
RS=(packages/rust/target/debug/urim)
PYC=("$PY" -m urim)
fail=0; n=0
mapfile -t paths < <("$PY" -c 'import json;[print("fixtures/"+c["path"]) for c in json.load(open("fixtures/cases.json"))["cases"]]')
paths+=("--version" "")
for p in "${paths[@]}"; do
  n=$((n+1))
  if [[ "$p" == "--version" ]]; then args=(--version); elif [[ -z "$p" ]]; then args=(); else args=(check "$p"); fi
  ref=""
  for impl in JS RS PYC; do
    declare -n cmd=$impl
    out=$("${cmd[@]}" "${args[@]}" 2>/tmp/urim-parity-err) && code=0 || code=$?
    got="exit=$code|out=$out|err=$(cat /tmp/urim-parity-err)"
    if [[ -z "$ref" ]]; then ref=$got; elif [[ "$got" != "$ref" ]]; then
      echo "MISMATCH [$impl] ${args[*]}"; echo "  ref: $ref"; echo "  got: $got"; fail=1
    fi
  done
done
[[ $fail -eq 0 ]] && echo "parity OK: $n invocations x 3 implementations identical" || exit 1
