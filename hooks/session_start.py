"""Session start hook — check for active experiments and show status."""

import os
import sys
import json


def main():
    # Try to find active experiments in current working directory
    cwd = os.getcwd()
    experiments_file = os.path.join(cwd, ".worktrees", "experiments.json")

    if not os.path.exists(experiments_file):
        return

    try:
        with open(experiments_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    experiments = data.get("experiments", {})
    active = [e for e in experiments.values() if e.get("status") in ("running", "evaluating", "evaluated")]

    if not active:
        return

    lines = ["[worktrees] Active experiments found:"]
    for exp in active:
        passed = sum(1 for v in exp["variants"] if v.get("status") == "passed")
        failed = sum(1 for v in exp["variants"] if v.get("status") == "failed")
        pending = sum(1 for v in exp["variants"] if v.get("status") in ("pending", "in_progress"))
        lines.append(
            f"  - {exp['id']}: {exp['description']} "
            f"[{exp['status']}] "
            f"({exp['num_variants']} variants: {passed} passed, {failed} failed, {pending} pending)"
        )

    if any(e["status"] == "evaluated" for e in active):
        lines.append("  Tip: Use evaluate_variants or merge_variant to continue.")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
