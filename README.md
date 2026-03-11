# claude-worktrees

Try N approaches to a problem in parallel, evaluate them, merge the winner.

Each approach runs in an isolated git worktree with its own branch. Claude works on all variants simultaneously, then runs your test suite to compare results.

## Install

```bash
/plugin install claude-worktrees
```

## Usage

```
/experiment "optimize the database query layer" --eval "npm test"
```

That's it. Claude will:
1. Create isolated git worktrees (one per approach)
2. Work on each variant in parallel
3. Run your tests in every worktree
4. Show you which passed, which failed, and how fast
5. Ask which one to merge

### Options

```
/experiment "description"
  --variants 3          # number of approaches (default: 3, max: 5)
  --eval "npm test"     # eval command (auto-detected if omitted)
  --hints "use redis" "use LRU" "use SQLite"  # approach hints
```

### MCP tools

If you prefer manual control, the plugin exposes these tools:

| Tool | Description |
|------|-------------|
| `experiment_start` | Create N worktrees for parallel approaches |
| `experiment_eval` | Run eval command in all worktrees and rank results |
| `experiment_diff` | Show git diff for a variant vs base |
| `experiment_merge` | Merge winning variant and clean up |
| `experiment_cleanup` | Remove all worktrees without merging |
| `experiment_list` | List all experiments with status |
| `experiment_status` | Detailed status of one experiment |

## How it works

```
your-project/
├── .worktrees/
│   ├── experiments.json          # tracks all experiments
│   ├── exp-a1b2c3d4-1/          # variant 1 worktree
│   ├── exp-a1b2c3d4-2/          # variant 2 worktree
│   └── exp-a1b2c3d4-3/          # variant 3 worktree
```

Each worktree is a full copy of your repo on its own branch (`experiment/{id}/variant-{n}`). Changes in one worktree don't affect others. When you merge a winner, the others get cleaned up automatically.

## Requirements

- Python 3.10+
- Git
- No pip dependencies (pure stdlib)
