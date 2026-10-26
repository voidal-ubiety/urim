#!/usr/bin/env bash
# One command for the whole living contract: tests with 100% coverage in all three
# languages, cross-language parity, and the CONTRACT.md <-> tests cross-check.
#
#   scripts/verify.sh            # from anywhere in the checkout
#
# Needs: node >= 20 + npm; uv (or $PYTHON pointing at a venv with `--group dev`
# installed); cargo + cargo-llvm-cov (nightly toolchain for branch coverage).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ -d "$HOME/.cargo/bin" ]] && PATH="$HOME/.cargo/bin:$PATH"
step() { printf '\n==> %s\n' "$*"; }

# ---------- JS ----------
step "js: install"
cd "$ROOT/packages/js"
[[ -d node_modules ]] || npm ci --no-audit --no-fund
step "js: tests + c8 coverage (100% lines/branches/functions/statements)"
npm run -s coverage

# ---------- Python ----------
cd "$ROOT/packages/python"
if [[ -z "${PYTHON:-}" ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    step "python: create .venv (uv)"
    uv venv -q .venv && uv pip install -q -p .venv/bin/python -e . --group dev
  fi
  PYTHON="$ROOT/packages/python/.venv/bin/python"
fi
step "python: pytest + coverage (branch, fail_under=100)"
"$PYTHON" -m pytest -q -W error --cov --cov-report=term-missing

# ---------- Rust ----------
cd "$ROOT/packages/rust"
step "rust: build (debug binary used by parity)"
cargo build -q
if cargo +nightly --version >/dev/null 2>&1; then
  step "rust: tests + llvm-cov on nightly (100% lines/regions/functions + branches)"
  cargo +nightly llvm-cov -q --branch --json --summary-only --output-path target/llvm-cov-summary.json \
    --fail-under-lines 100 --fail-under-regions 100 --fail-under-functions 100
  python3 - target/llvm-cov-summary.json <<'PY'
import json, sys
t = json.load(open(sys.argv[1]))["data"][0]["totals"]
for k in ("lines", "regions", "functions", "branches"):
    print(f"  {k:9} {t[k]['covered']}/{t[k]['count']} = {t[k]['percent']:.2f}%")
b = t["branches"]
sys.exit(0 if b["covered"] == b["count"] else "rust: branch coverage below 100%")
PY
else
  step "rust: tests + llvm-cov on stable (no nightly: lines/regions/functions only, no branch coverage)"
  cargo llvm-cov -q --summary-only --fail-under-lines 100 --fail-under-regions 100 --fail-under-functions 100
fi

# ---------- Cross-language ----------
cd "$ROOT"
step "parity: byte-identical CLIs"
PYTHON="$PYTHON" scripts/parity.sh
step "contract-check: every CONTRACT.md ID tested in every language"
python3 scripts/contract-check.py
printf '\nverify OK\n'
