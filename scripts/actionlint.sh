#!/usr/bin/env bash
# Lint GitHub Actions workflow files with actionlint.
#
# Requires: actionlint (https://github.com/rhysd/actionlint)
#   brew install actionlint
#
# Usage:
#   ./scripts/actionlint.sh

set -euo pipefail

if ! command -v actionlint &>/dev/null; then
    echo >&2 "ERROR: actionlint not found. Install with: brew install actionlint"
    exit 1
fi

echo "Running actionlint..."
actionlint "$@"
echo "actionlint: OK"
