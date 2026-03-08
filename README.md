# claude-worktrees

Parallel experiment orchestrator for Claude Code. Try N different approaches to a problem in isolated git worktrees, evaluate each, merge the winner.

## Concept

When solving a problem, there are often multiple viable approaches. Instead of trying one, backing up, and trying another, `claude-worktrees` lets you:

1. **Fork** — Create N parallel git worktrees, each on its own branch
2. **Work** — Implement a different approach in each worktree
3. **Evaluate** — Run your test/benchmark suite in each worktree
4. **Merge** — Pick the winner and merge it back

Think of it as A/B testing for code changes.

## Installation

Pure Python stdlib — no dependencies needed.

```bash
bash install.sh   # Linux/macOS
# or
powershell install.ps1  # Windows
```

Requires Python 3.10+ and git.

## MCP Tools

### start_experiment
Create N parallel worktrees to try different approaches.

```
project_path: "/path/to/project"
description: "Add caching layer to API"
num_variants: 3
eval_cmd: "npm test && npm run bench"
variant_hints: ["use Redis", "use in-memory LRU", "use disk cache"]
```

### run_variant
Get the worktree path and formatted prompt for a specific variant.

```
project_path: "/path/to/project"
experiment_id: "abc12345"
variant: 1
prompt: "Add a caching layer to the API endpoints"
```

### evaluate_variants
Run the eval command in each worktree and compare results.

```
project_path: "/path/to/project"
experiment_id: "abc12345"
```

### get_variant_diff
Show the git diff for a variant vs the base branch.

### merge_variant
Merge the winning variant and clean up everything else.

### cleanup_experiment
Remove all worktrees and branches without merging.

### list_experiments
List all experiments with their status.

### experiment_status
Detailed status of a specific experiment.

## Workflow Example

```
User: "I need to optimize the search function. Try 3 approaches."

1. start_experiment → creates 3 worktrees
2. run_variant(1) → "Use binary search"
3. run_variant(2) → "Use hash table lookup"
4. run_variant(3) → "Use trie data structure"
5. [Claude works in each worktree]
6. evaluate_variants → runs tests in each, ranks results
7. merge_variant(2) → hash table was fastest, merge it
```

## File Structure

```
.worktrees/                    # Created in your project (add to .gitignore)
  experiments.json             # Experiment state
  exp-{id}-1/                  # Worktree for variant 1
  exp-{id}-2/                  # Worktree for variant 2
  ...
```

## Constraints

- Pure Python stdlib — zero pip dependencies
- All git operations via subprocess
- The plugin does NOT run Claude in worktrees — it sets up worktrees and provides prompts. You or Claude orchestrates which variant to work on.
- Cleanup is thorough: removes worktrees AND branches
