# claude-worktrees

When the user asks to try multiple approaches, compare implementations, or experiment with different solutions, use the worktrees MCP tools.

## Workflow

1. Call `experiment_start` with a description, number of variants, eval command, and optional approach hints
2. For each variant, spawn an **Agent** (using the Agent tool) to work in that variant's `worktree_path`. Launch ALL agents in a single message so they run in parallel. Each agent should:
   - Only edit files inside its worktree_path
   - Follow its assigned approach/hint
   - Commit changes when done
3. After all agents complete, call `experiment_eval` to run tests in all worktrees
4. Present the results to the user — which passed, which failed, timing
5. Ask the user which variant to merge, then call `experiment_merge`

## Triggers

Use this when the user says things like:
- "try 3 different approaches to..."
- "experiment with..."
- "compare different ways to..."
- "A/B test this change"
- "which approach would be better for..."

## Example agent prompt

For each variant, the agent prompt should be:
```
Working directory: {worktree_path}
Task: {description}
Approach: {hint}

Make all file changes in {worktree_path}. Commit your changes when done.
```
