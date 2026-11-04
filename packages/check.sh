#!/usr/bin/env bash
# One gate for both ports (TypeScript, Python): tests, lint and types. Local only (no network, no publish).
#   PYTHONS="/path/py3.11 /path/py3.13" TOOLS=/path/venv/bin bash packages/check.sh
# PYTHONS: interpreters to run pytest under (default: python3). TOOLS: dir holding ruff and mypy
# (default: the first interpreter's bin dir).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
read -r -a pythons <<< "${PYTHONS:-python3}"
tools="${TOOLS:-$(dirname "${pythons[0]}")}"

step() { printf '\n== %s\n' "$*"; }

step "no tracked drafts/ or research/"
if [ -x "$here/../scripts/maintainer-checks.sh" ]; then
  # Maintainers' source repo: it tracks these on purpose and runs its own checks instead.
  echo "maintainer checks"
  "$here/../scripts/maintainer-checks.sh" "${pythons[0]}"
else
  "$here/../scripts/check-internal-paths"
fi
step "vendor name only in provider source"
"$here/../scripts/check-provider-names"
"${pythons[0]}" -m pytest -q -p no:cacheprovider "$here/../scripts/tests/test_check_internal_paths.py" "$here/../scripts/tests/test_check_provider_names.py" "$here/../scripts/tests/test_dev.py"

cd "$here/urim-py"
for py in "${pythons[@]}"; do
  step "pytest ($("$py" -V))"
  "$py" -m pytest -q tests
done
step "ruff check";        "$tools/ruff" check .
step "ruff format --check"; "$tools/ruff" format --check .
step "mypy --strict";     "$tools/mypy"

cd "$here/urim-ts"
step "npm test";          npm test --silent
step "tsc --noEmit";      npx tsc --noEmit -p .
step "all checks passed"
