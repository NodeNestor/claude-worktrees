#!/bin/bash
# Spawn a single variant worktree for an experiment.
# Usage: spawn_variant.sh <project_path> <experiment_id> <variant_number>

set -e

PROJECT_PATH="$1"
EXPERIMENT_ID="$2"
VARIANT_NUM="$3"

if [ -z "$PROJECT_PATH" ] || [ -z "$EXPERIMENT_ID" ] || [ -z "$VARIANT_NUM" ]; then
    echo "Usage: spawn_variant.sh <project_path> <experiment_id> <variant_number>" >&2
    exit 1
fi

WORKTREE_DIR="$PROJECT_PATH/.worktrees"
WORKTREE_PATH="$WORKTREE_DIR/exp-${EXPERIMENT_ID}-${VARIANT_NUM}"
BRANCH_NAME="experiment/${EXPERIMENT_ID}/variant-${VARIANT_NUM}"

mkdir -p "$WORKTREE_DIR"

cd "$PROJECT_PATH"

if [ -d "$WORKTREE_PATH" ]; then
    echo "Worktree already exists: $WORKTREE_PATH"
    exit 0
fi

git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"

if [ $? -eq 0 ]; then
    echo "Created worktree: $WORKTREE_PATH (branch: $BRANCH_NAME)"
else
    echo "Failed to create worktree" >&2
    exit 1
fi
