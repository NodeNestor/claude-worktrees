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

server = MCPServer("claude-worktrees", "2.0.0")


def _gen_id(description: str) -> str:
    h = hashlib.sha256(f"{description}{time.time()}".encode()).hexdigest()[:8]
    return h


def _project_path() -> str:
    """Get project path from environment or cwd."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


# --- Tools ---

@server.tool(
    "experiment_start",
    "Create N parallel git worktrees to try different approaches to a problem. "
    "Each worktree gets its own branch. After working on variants, use experiment_eval to compare them.",
    {
        "properties": {
            "description": {"type": "string", "description": "What this experiment is trying to solve"},
            "num_variants": {"type": "integer", "description": "Number of parallel approaches (2-5)"},
            "eval_cmd": {"type": "string", "description": "Command to evaluate each variant (e.g. 'npm test', 'python -m pytest')"},
            "variant_hints": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Approach hint for each variant, e.g. ['use redis', 'use LRU cache', 'use SQLite']",
            },
        },
        "required": ["description", "num_variants", "eval_cmd"],
    },
)
def experiment_start(
    description: str,
    num_variants: int,
    eval_cmd: str,
    variant_hints: list[str] | None = None,
):
    project_path = _project_path()
    num_variants = max(2, min(5, num_variants))
    experiment_id = _gen_id(description)
    mgr = WorktreeManager(project_path)

    result = mgr.create_experiment(experiment_id, num_variants)
    if result["errors"]:
        return {"success": False, "experiment_id": experiment_id, "errors": result["errors"]}

    state_create(
        project_path=project_path,
        experiment_id=experiment_id,
        description=description,
        num_variants=num_variants,
        eval_cmd=eval_cmd,
        base_branch=result["base_branch"],
        variant_hints=variant_hints,
    )

    variants = []
    for v in result["variants"]:
        hint = variant_hints[v["id"] - 1] if variant_hints and v["id"] <= len(variant_hints) else None
        variants.append({
            "variant": v["id"],
            "branch": v["branch"],
            "worktree_path": v["path"],
            "hint": hint,
        })

    return {
        "success": True,
        "experiment_id": experiment_id,
        "description": description,
        "base_branch": result["base_branch"],
        "eval_cmd": eval_cmd,
        "variants": variants,
    }


@server.tool(
    "experiment_eval",
    "Run the eval command in each variant's worktree and rank results. "
    "Shows which variants passed, their timing, and recommends the winner.",
    {
        "properties": {
            "experiment_id": {"type": "string", "description": "Experiment ID"},
        },
        "required": ["experiment_id"],
    },
)
def experiment_eval(experiment_id: str):
    project_path = _project_path()
    exp = get_experiment(project_path, experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}

    update_experiment(project_path, experiment_id, {"status": "evaluating"})

    mgr = WorktreeManager(project_path)
    results = mgr.evaluate_all(experiment_id, exp["eval_cmd"])

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

    passed = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    return {
        "experiment_id": experiment_id,
        "eval_cmd": exp["eval_cmd"],
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "results": results,
        "recommendation": (
            f"Variant {passed[0]['variant']} is the fastest passing variant "
            f"({passed[0]['duration_seconds']}s). Use experiment_merge to merge it."
            if passed else "No variants passed. Review errors and fix or retry."
        ),
    }


@server.tool(
    "experiment_diff",
    "Show the git diff for a variant compared to the base branch.",
    {
        "properties": {
            "experiment_id": {"type": "string", "description": "Experiment ID"},
            "variant": {"type": "integer", "description": "Variant number"},
        },
        "required": ["experiment_id", "variant"],
    },
)
def experiment_diff(experiment_id: str, variant: int):
    project_path = _project_path()
    mgr = WorktreeManager(project_path)
    diff = mgr.get_variant_diff(experiment_id, variant)
    return {"experiment_id": experiment_id, "variant": variant, "diff": diff}


@server.tool(
    "experiment_merge",
    "Merge the winning variant into the base branch and clean up all worktrees.",
    {
        "properties": {
            "experiment_id": {"type": "string", "description": "Experiment ID"},
            "variant": {"type": "integer", "description": "Variant number to merge"},
        },
        "required": ["experiment_id", "variant"],
    },
)
def experiment_merge(experiment_id: str, variant: int):
    project_path = _project_path()
    mgr = WorktreeManager(project_path)

    merge_result = mgr.merge_variant(experiment_id, variant)
    if not merge_result.get("success"):
        return merge_result

    cleanup_result = mgr.cleanup_experiment(experiment_id)
    update_experiment(project_path, experiment_id, {"status": "merged"})

    return {
        "success": True,
        "merged_variant": variant,
        "merge": merge_result,
        "cleanup": cleanup_result,
    }


@server.tool(
    "experiment_cleanup",
    "Remove all worktrees and branches for an experiment without merging.",
    {
        "properties": {
            "experiment_id": {"type": "string", "description": "Experiment ID"},
        },
        "required": ["experiment_id"],
    },
)
def experiment_cleanup(experiment_id: str):
    project_path = _project_path()
    mgr = WorktreeManager(project_path)
    result = mgr.cleanup_experiment(experiment_id)
    delete_experiment(project_path, experiment_id)
    return {"success": True, "experiment_id": experiment_id, **result}


@server.tool(
    "experiment_list",
    "List all experiments in the current project with status.",
    {
        "properties": {},
        "required": [],
    },
)
def experiment_list():
    project_path = _project_path()
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
        })

    return {"experiments": summary}


@server.tool(
    "experiment_status",
    "Show detailed status of an experiment and all its variants.",
    {
        "properties": {
            "experiment_id": {"type": "string", "description": "Experiment ID"},
        },
        "required": ["experiment_id"],
    },
)
def experiment_status(experiment_id: str):
    project_path = _project_path()
    exp = get_experiment(project_path, experiment_id)
    if not exp:
        return {"error": f"Experiment {experiment_id} not found"}
    return exp


if __name__ == "__main__":
    server.run()
