"""MCP server for claude-worktrees — parallel experiment orchestrator."""

import os
import sys
import hashlib
import time

# Add parent to path so imports work when run from plugin root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_stdio import MCPServer
from worktree_manager import WorktreeManager
from experiment_state import (
    create_experiment as state_create,
    get_experiment,
    update_experiment,
    update_variant,
    delete_experiment,
    list_experiments as state_list,
)

server = MCPServer("claude-worktrees", "1.0.0")


def _gen_id(description: str) -> str:
    """Generate a short experiment ID from description + timestamp."""
    h = hashlib.sha256(f"{description}{time.time()}".encode()).hexdigest()[:8]
    return h


# --- Tools ---

@server.tool(
    "start_experiment",
    "Create N parallel worktrees to try different approaches to a problem. "
    "Returns experiment ID and worktree paths. Use run_variant to get prompts for each.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "description": {"type": "string", "description": "What this experiment is trying to solve"},
            "num_variants": {"type": "integer", "description": "Number of parallel approaches to try (2-10)"},
            "eval_cmd": {"type": "string", "description": "Command to evaluate each variant (e.g. 'npm test', 'python -m pytest')"},
            "variant_hints": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional hints for each variant, e.g. ['use redis caching', 'use in-memory LRU', 'use disk cache']",
            },
        },
        "required": ["project_path", "description", "num_variants", "eval_cmd"],
    },
)
def start_experiment(
    project_path: str,
    description: str,
    num_variants: int,
    eval_cmd: str,
    variant_hints: list[str] | None = None,
):
    num_variants = max(2, min(10, num_variants))
    experiment_id = _gen_id(description)
    mgr = WorktreeManager(project_path)

    # Create worktrees
    result = mgr.create_experiment(experiment_id, num_variants)
    if result["errors"]:
        return {
            "success": False,
            "experiment_id": experiment_id,
            "errors": result["errors"],
        }

    # Save state
    state_create(
        project_path=project_path,
        experiment_id=experiment_id,
        description=description,
        num_variants=num_variants,
        eval_cmd=eval_cmd,
        base_branch=result["base_branch"],
        variant_hints=variant_hints,
    )

    # Build response
    variants_info = []
    for v in result["variants"]:
        hint = None
        if variant_hints and v["id"] <= len(variant_hints):
            hint = variant_hints[v["id"] - 1]
        variants_info.append({
            "variant": v["id"],
            "branch": v["branch"],
            "path": v["path"],
            "hint": hint,
        })

    return {
        "success": True,
        "experiment_id": experiment_id,
        "description": description,
        "base_branch": result["base_branch"],
        "eval_cmd": eval_cmd,
        "variants": variants_info,
        "next_step": f"Use run_variant to get a working prompt for each variant. "
                     f"Work on each variant by editing files in its worktree path.",
    }


@server.tool(
    "experiment_status",
    "Show the current status of an experiment and all its variants.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "experiment_id": {"type": "string", "description": "Experiment ID"},
        },
        "required": ["project_path", "experiment_id"],
    },
)
def experiment_status(project_path: str, experiment_id: str):
    exp = get_experiment(project_path, experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}
    return exp


@server.tool(
    "run_variant",
    "Get the worktree path and a formatted prompt for working on a specific variant. "
    "Use this to know WHERE to make changes and WHAT approach to take.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "experiment_id": {"type": "string", "description": "Experiment ID"},
            "variant": {"type": "integer", "description": "Variant number (1-based)"},
            "prompt": {"type": "string", "description": "The task prompt — what to implement in this variant"},
        },
        "required": ["project_path", "experiment_id", "variant", "prompt"],
    },
)
def run_variant(project_path: str, experiment_id: str, variant: int, prompt: str):
    exp = get_experiment(project_path, experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}

    variant_info = None
    for v in exp["variants"]:
        if v["id"] == variant:
            variant_info = v
            break
    if not variant_info:
        return {"error": f"Variant {variant} not found"}

    mgr = WorktreeManager(project_path)
    worktree_path = mgr.get_worktree_path(experiment_id, variant)

    if not os.path.isdir(worktree_path):
        return {"error": f"Worktree path does not exist: {worktree_path}"}

    # Update variant status
    update_variant(project_path, experiment_id, variant, {"status": "in_progress"})

    hint_text = ""
    if variant_info.get("hint"):
        hint_text = f"\n\nAPPROACH HINT: {variant_info['hint']}"

    formatted_prompt = (
        f"## Experiment: {exp['description']}\n"
        f"## Variant {variant} of {exp['num_variants']}\n"
        f"## Working directory: {worktree_path}\n"
        f"## Branch: {variant_info['branch']}\n"
        f"{hint_text}\n\n"
        f"IMPORTANT: All file edits for this variant MUST be in:\n"
        f"  {worktree_path}\n\n"
        f"TASK:\n{prompt}\n\n"
        f"When done, the variant will be evaluated with:\n"
        f"  {exp['eval_cmd']}"
    )

    return {
        "worktree_path": worktree_path,
        "branch": variant_info["branch"],
        "variant": variant,
        "hint": variant_info.get("hint"),
        "prompt": formatted_prompt,
    }


@server.tool(
    "evaluate_variants",
    "Run the eval command in each variant's worktree and compare results. "
    "Returns a ranked comparison showing which variants passed and their timing.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "experiment_id": {"type": "string", "description": "Experiment ID"},
        },
        "required": ["project_path", "experiment_id"],
    },
)
def evaluate_variants(project_path: str, experiment_id: str):
    exp = get_experiment(project_path, experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}

    update_experiment(project_path, experiment_id, {"status": "evaluating"})

    mgr = WorktreeManager(project_path)
    results = mgr.evaluate_all(experiment_id, exp["eval_cmd"])

    # Update variant states
    for r in results:
        status = "passed" if r.get("success") else "failed"
        update_variant(project_path, experiment_id, r["variant"], {
            "status": status,
            "eval_result": {
                "success": r.get("success", False),
                "exit_code": r.get("exit_code"),
                "duration_seconds": r.get("duration_seconds"),
                "stdout_tail": (r.get("stdout", ""))[-500:],
                "stderr_tail": (r.get("stderr", ""))[-500:],
            },
        })

    update_experiment(project_path, experiment_id, {"status": "evaluated"})

    # Build comparison
    passed = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    return {
        "experiment_id": experiment_id,
        "eval_cmd": exp["eval_cmd"],
        "total_variants": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "results": results,
        "recommendation": (
            f"Variant {passed[0]['variant']} is the fastest passing variant "
            f"({passed[0]['duration_seconds']}s). Use merge_variant to merge it."
            if passed else "No variants passed. Review the errors and try again."
        ),
    }


@server.tool(
    "get_variant_diff",
    "Show the git diff for a specific variant compared to the base branch.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "experiment_id": {"type": "string", "description": "Experiment ID"},
            "variant": {"type": "integer", "description": "Variant number"},
        },
        "required": ["project_path", "experiment_id", "variant"],
    },
)
def get_variant_diff(project_path: str, experiment_id: str, variant: int):
    mgr = WorktreeManager(project_path)
    diff = mgr.get_variant_diff(experiment_id, variant)
    return {
        "experiment_id": experiment_id,
        "variant": variant,
        "diff": diff,
    }


@server.tool(
    "merge_variant",
    "Merge the winning variant into the base branch and clean up all other worktrees/branches.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "experiment_id": {"type": "string", "description": "Experiment ID"},
            "variant": {"type": "integer", "description": "Variant number to merge"},
        },
        "required": ["project_path", "experiment_id", "variant"],
    },
)
def merge_variant(project_path: str, experiment_id: str, variant: int):
    mgr = WorktreeManager(project_path)

    # Merge the winner
    merge_result = mgr.merge_variant(experiment_id, variant)
    if not merge_result.get("success"):
        return merge_result

    # Clean up all worktrees and branches
    cleanup_result = mgr.cleanup_experiment(experiment_id)

    # Update state
    update_experiment(project_path, experiment_id, {"status": "merged"})

    return {
        "success": True,
        "merged_variant": variant,
        "merge": merge_result,
        "cleanup": cleanup_result,
    }


@server.tool(
    "cleanup_experiment",
    "Remove all worktrees and branches for an experiment without merging anything.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
            "experiment_id": {"type": "string", "description": "Experiment ID"},
        },
        "required": ["project_path", "experiment_id"],
    },
)
def cleanup_experiment(project_path: str, experiment_id: str):
    mgr = WorktreeManager(project_path)
    result = mgr.cleanup_experiment(experiment_id)
    delete_experiment(project_path, experiment_id)
    return {
        "success": True,
        "experiment_id": experiment_id,
        **result,
    }


@server.tool(
    "list_experiments",
    "List all experiments in a project with their current status.",
    {
        "properties": {
            "project_path": {"type": "string", "description": "Absolute path to the git project root"},
        },
        "required": ["project_path"],
    },
)
def list_experiments(project_path: str):
    experiments = state_list(project_path)
    if not experiments:
        return {"experiments": [], "message": "No active experiments."}

    summary = []
    for exp in experiments:
        passed = sum(1 for v in exp["variants"] if v.get("status") == "passed")
        failed = sum(1 for v in exp["variants"] if v.get("status") == "failed")
        pending = sum(1 for v in exp["variants"] if v.get("status") in ("pending", "in_progress"))
        summary.append({
            "id": exp["id"],
            "description": exp["description"],
            "status": exp["status"],
            "variants": exp["num_variants"],
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "created": exp["created"],
        })

    return {"experiments": summary}


if __name__ == "__main__":
    server.run()
