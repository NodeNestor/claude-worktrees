#!/bin/bash
# Install claude-worktrees plugin — pure stdlib, no venv needed.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "claude-worktrees: Pure Python stdlib — no dependencies to install."
echo ""

# Verify Python 3.10+ is available
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "ERROR: Python not found. Install Python 3.10+." >&2
    exit 1
fi

VERSION=$($PY -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$($PY -c "import sys; print(sys.version_info.major)")
MINOR=$($PY -c "import sys; print(sys.version_info.minor)")

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo "ERROR: Python 3.10+ required (found $VERSION)." >&2
    exit 1
fi

echo "Python $VERSION found. Ready to use."
echo ""
echo "Plugin installed at: $SCRIPT_DIR"
echo "Add to your Claude Code plugins or use the MCP server directly."
