"""Track experiment state in JSON files — zero dependencies."""

import os
import json
from datetime import datetime, timezone


EXPERIMENTS_FILE = "experiments.json"


def _experiments_path(project_path: str) -> str:
    return os.path.join(project_path, ".worktrees", EXPERIMENTS_FILE)


def _load_experiments(project_path: str) -> dict:
    path = _experiments_path(project_path)
    if not os.path.exists(path):
        return {"experiments": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_experiments(project_path: str, data: dict):
    path = _experiments_path(project_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_experiment(
    project_path: str,
    experiment_id: str,
    description: str,
    num_variants: int,
    eval_cmd: str,
    base_branch: str,
    variant_hints: list[str] | None = None,
) -> dict:
    data = _load_experiments(project_path)
    variants = []
    for i in range(1, num_variants + 1):
        hint = variant_hints[i - 1] if variant_hints and i <= len(variant_hints) else None
        variants.append({
            "id": i,
            "branch": f"experiment/{experiment_id}/variant-{i}",
            "status": "pending",
            "hint": hint,
            "eval_result": None,
        })

    experiment = {
        "id": experiment_id,
        "description": description,
        "created": datetime.now(timezone.utc).isoformat(),
        "num_variants": num_variants,
        "eval_cmd": eval_cmd,
        "base_branch": base_branch,
        "status": "running",
        "variants": variants,
    }
    data["experiments"][experiment_id] = experiment
    _save_experiments(project_path, data)
    return experiment


def get_experiment(project_path: str, experiment_id: str) -> dict | None:
    data = _load_experiments(project_path)
    return data["experiments"].get(experiment_id)


def update_experiment(project_path: str, experiment_id: str, updates: dict):
    data = _load_experiments(project_path)
    if experiment_id not in data["experiments"]:
        return
    data["experiments"][experiment_id].update(updates)
    _save_experiments(project_path, data)


def update_variant(project_path: str, experiment_id: str, variant_id: int, updates: dict):
    data = _load_experiments(project_path)
    exp = data["experiments"].get(experiment_id)
    if not exp:
        return
    for v in exp["variants"]:
        if v["id"] == variant_id:
            v.update(updates)
            break
    _save_experiments(project_path, data)


def delete_experiment(project_path: str, experiment_id: str):
    data = _load_experiments(project_path)
    data["experiments"].pop(experiment_id, None)
    _save_experiments(project_path, data)


def list_experiments(project_path: str) -> list[dict]:
    data = _load_experiments(project_path)
    return list(data["experiments"].values())
