#!/usr/bin/env bash
# The single gate. Lint, type-check and format-check all three ports; run their tests
# at 100% coverage; check cross-language parity and the CONTRACT.md <-> tests mapping.
# Any failure stops the script with a non-zero exit.
#
#   scripts/verify.sh            # from anywhere in the checkout
#
#   scripts/verify.sh --release  # also the release-only gates (DCO, audit-legal --release)
#
# Needs: node >= 22 + npm; uv (or $PYTHON pointing at a venv with `--group dev`
# installed); rustup with stable (+clippy, rustfmt), nightly (branch coverage) and
# 1.85.0 (MSRV) toolchains; cargo-llvm-cov, cargo-deny, cargo-audit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE=0
case "${1:-}" in
  "") ;;
  --release) RELEASE=1 ;;
  *) echo "usage: scripts/verify.sh [--release]" >&2; exit 2 ;;
esac
[[ -d "$HOME/.cargo/bin" ]] && PATH="$HOME/.cargo/bin:$PATH"
step() { printf '\n==> %s\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { printf 'verify: missing %s (%s)\n' "$1" "$2" >&2; exit 1; }; }

# ---------- Sources, copies and generated files (fast; fail first) ----------
cd "$ROOT"
step "spec: spec/ is an exact copy of upstream decision-contract-spec (scripts/sync-spec)"
python3 scripts/sync-spec
step "project: one version everywhere, SPEC version = protocol, URLs from config/project.json"
python3 scripts/check-project
step "deps: locked runtime closure = config/deps-allowlist.json (scripts/check-deps)"
python3 scripts/check-deps
step "generated: schema ports, mutation fixtures, sealed lockfiles are up to date"
python3 scripts/gen-schema --check
python3 scripts/gen-mutations --check
python3 scripts/seal-fixtures --check
if command -v uv >/dev/null 2>&1; then
  step "jcs: corpus agrees with the independent rfc8785 package"
  scripts/check-jcs-corpus
else
  step "jcs: SKIP corpus cross-check (needs uv)"
fi

# ---------- JS ----------
step "js: install"
cd "$ROOT/packages/js"
[[ -d node_modules ]] || npm ci --ignore-scripts --no-audit --no-fund
step "js: biome lint + format check, tsc --strict"
npm run -s lint
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
step "python: ruff check, ruff format --check, mypy --strict"
"$PYTHON" -m ruff check -q .
"$PYTHON" -m ruff format -q --check .
"$PYTHON" -m mypy
step "python: pytest + coverage (branch, fail_under=100)"
"$PYTHON" -m pytest -q -W error --cov --cov-report=term-missing

# ---------- Rust ----------
cd "$ROOT/packages/rust"
need cargo-deny "cargo install --locked cargo-deny"
need cargo-audit "cargo install --locked cargo-audit"
step "rust: cargo fmt --check, clippy -D warnings (pedantic/nursery/cargo + restriction set)"
cargo fmt --check
cargo clippy -q --all-targets --all-features -- -D warnings
step "rust: rustdoc -D warnings + doctests"
RUSTDOCFLAGS="-D warnings" cargo doc -q --no-deps
cargo test -q --doc
step "rust: MSRV 1.85 build"
cargo +1.85.0 check -q --all-targets --target-dir target/msrv
step "rust: cargo deny (advisories, licenses, bans, sources) + cargo audit"
cargo deny -L error check
cargo audit -q -D warnings
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
step "hostile: hostile inputs under time/RSS bounds, no execution (scripts/hostile.py)"
PYTHON="$PYTHON" python3 scripts/hostile.py
if command -v strace >/dev/null; then
  step "sandbox: no network, child processes or file writes under strace (scripts/check-sandbox)"
  python3 scripts/check-sandbox
elif [[ $RELEASE == 1 ]]; then
  echo "verify --release: strace is required for scripts/check-sandbox" >&2; exit 2
else
  step "sandbox: SKIP (needs strace)"
fi
step "contract-check: every CONTRACT.md ID tested in every language"
python3 scripts/contract-check.py
step "names: the pre-0.1 version-key name appears only where allowed (C-093)"
python3 scripts/check-names
step "people: .github/CODEOWNERS generated from config/people.yaml (scripts/gen-codeowners)"
"$PYTHON" scripts/gen-codeowners --check
# The scripts below import yaml, so they run on the Python port's locked venv (pyyaml from uv.lock).
step "scripts: unit tests for the repo scripts (audit-legal L5-Py, ...)"
"$PYTHON" -m unittest discover -q -s scripts/tests
if [[ $RELEASE == 1 ]]; then
  # Expected to FAIL until David's history rewrite (RELEASE-RUNBOOK §3a): the old commits
  # use the placeholder author email (audit-legal M3) and carry no Signed-off-by (DCO).
  step "release: DCO sign-off on every commit (scripts/check-dco)"
  python3 scripts/check-dco
  step "release: legal gate (scripts/audit-legal --release)"
  "$PYTHON" scripts/audit-legal --release
fi
printf '\nverify OK%s\n' "$([[ $RELEASE == 1 ]] && echo ' (release)')"
