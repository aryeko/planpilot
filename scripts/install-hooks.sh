#!/usr/bin/env bash
# Install local git hooks for the planpilot repository.
#
# Run once after cloning:
#   ./scripts/install-hooks.sh

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
SCRIPTS_DIR="$REPO_ROOT/scripts"

echo "Installing git hooks..."

# commit-msg hook — conventional commit linting
cp "$SCRIPTS_DIR/commit-msg" "$HOOKS_DIR/commit-msg"
chmod +x "$HOOKS_DIR/commit-msg"
echo "  ✓ commit-msg hook installed"

# Verify commitlint is available via poetry
if poetry run commitlint --version &>/dev/null; then
    echo "  ✓ commitlint available (poetry dev dependency)"
else
    echo "  ⚠ commitlint not found — run 'poetry install' first"
fi

echo ""
echo "Done. Hooks installed in $HOOKS_DIR"
