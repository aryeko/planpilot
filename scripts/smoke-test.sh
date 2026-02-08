#!/usr/bin/env bash
# scripts/smoke-test.sh — Install from TestPyPI and verify the package works.
#
# Usage:
#   PKG_VERSION=0.2.0 ./scripts/smoke-test.sh
#
# Required env:
#   PKG_VERSION  — the exact version to install and verify
#
# Optional env:
#   MAX_ATTEMPTS — number of install retries (default: 5)
#   PKG_NAME     — distribution name      (default: planpilot)
#   IMPORT_NAME  — importable module name  (default: planpilot)
set -euo pipefail

: "${PKG_VERSION:?PKG_VERSION is required}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-5}"
PKG_NAME="${PKG_NAME:-planpilot}"
IMPORT_NAME="${IMPORT_NAME:-planpilot}"

echo "=== Smoke test: ${PKG_NAME}==${PKG_VERSION} ==="

# ── 1. Create an isolated venv ──────────────────────────────────
python -m venv .smoke-venv
# shellcheck disable=SC1091
source .smoke-venv/bin/activate
python -m pip install -U pip --quiet

# ── 2. Install from TestPyPI (with retries for index lag) ───────
installed=false
for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
  echo "::group::Attempt ${attempt}/${MAX_ATTEMPTS}: pip install ${PKG_NAME}==${PKG_VERSION}"
  if python -m pip install \
      --index-url https://test.pypi.org/simple/ \
      --extra-index-url https://pypi.org/simple/ \
      "${PKG_NAME}==${PKG_VERSION}"; then
    installed=true
    echo "::endgroup::"
    break
  fi
  echo "::endgroup::"

  if [ "${attempt}" -eq "${MAX_ATTEMPTS}" ]; then
    echo "::error::Install from TestPyPI failed after ${MAX_ATTEMPTS} attempts"
    exit 1
  fi
  backoff=$((attempt * 10))
  echo "Retrying in ${backoff}s..."
  sleep "${backoff}"
done

if [ "${installed}" != "true" ]; then
  echo "::error::Install flag not set — unexpected state"
  exit 1
fi

# ── 3. Verify import + version ──────────────────────────────────
echo "--- Verifying import + __version__ ---"
python -c "
from ${IMPORT_NAME} import __version__
assert __version__ == '${PKG_VERSION}', (
    f'Version mismatch: expected ${PKG_VERSION}, got {__version__}'
)
print(f'${IMPORT_NAME} {__version__} imported OK')
"

# ── 4. Verify CLI entry point ───────────────────────────────────
echo "--- Verifying CLI entry point ---"
"${PKG_NAME}" --help > /dev/null
echo "${PKG_NAME} --help OK"

echo "=== Smoke test passed ==="
