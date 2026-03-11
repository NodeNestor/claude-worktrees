---
name: experiment
description: "Try N parallel approaches to a problem in isolated git worktrees, evaluate them, and merge the winner. Usage: /experiment <description> [--variants N] [--eval 'command'] [--hints 'hint1' 'hint2']"
user_invocable: true
---

# Experiment: Parallel approach testing

The user wants to try multiple approaches to a problem in parallel using isolated git worktrees.

## Parse the request

Extract from the user's message and arguments:
- **description**: What problem to solve (required)
- **variants**: Number of approaches to try (default: 3, max: 5)
- **eval_cmd**: Command to evaluate results (default: infer from project — `npm test`, `pytest`, `cargo test`, etc.)
- **hints**: Optional approach hints for each variant

If the user just said `/experiment "optimize the search"`, pick 3 sensible approaches yourself based on the problem.

## Step 1: Create the experiment

Call the `experiment_start` MCP tool with the parsed parameters. This creates isolated git worktrees — one per variant.

## Step 2: Work on each variant IN PARALLEL

For each variant returned by `experiment_start`, spawn an Agent using the Agent tool:

```
Agent(
  prompt="<the task with the variant's hint, working in the variant's worktree_path>",
  description="Variant N: <hint>",
  mode="bypassPermissions"
)
```

CRITICAL rules for each agent:
- Tell it the **exact worktree_path** where it must make all file changes
- Tell it the **approach/hint** to follow
- Tell it to **commit its changes** when done
- Launch ALL variant agents in a SINGLE message so they run in parallel

## Step 3: Evaluate

After all agents complete, call `experiment_eval` to run the eval command in each worktree. This ranks variants by pass/fail and speed.

## Step 4: Present results

Show the user a clear comparison:
- Which variants passed/failed
- Timing for each
- A brief summary of what each variant did differently

If any variant failed, offer to show the error output.

## Step 5: Ask the user

Ask which variant to merge (or suggest the recommended one). Then:
- `experiment_merge` to merge the winner
- Or `experiment_cleanup` to discard everything

Do NOT merge without asking the user first.
