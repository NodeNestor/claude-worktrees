"""Git worktree operations — pure subprocess calls, zero dependencies."""

import os
import subprocess
import time


class WorktreeManager:
    def __init__(self, project_path: str):
        self.project_path = os.path.abspath(project_path)
        self.worktrees_dir = os.path.join(self.project_path, ".worktrees")

    def _run_git(self, args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
        """Run a git command, return (returncode, stdout, stderr)."""
        cwd = cwd or self.project_path
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except FileNotFoundError:
            return 1, "", "git not found"

    def _get_current_branch(self) -> str:
        rc, out, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return out if rc == 0 else "main"

    def create_experiment(self, experiment_id: str, num_variants: int) -> dict:
        """Create N worktrees for an experiment."""
        os.makedirs(self.worktrees_dir, exist_ok=True)
        base_branch = self._get_current_branch()
        results = {"base_branch": base_branch, "variants": [], "errors": []}

        for i in range(1, num_variants + 1):
            branch_name = f"experiment/{experiment_id}/variant-{i}"
            worktree_path = os.path.join(self.worktrees_dir, f"exp-{experiment_id}-{i}")

            rc, out, err = self._run_git([
                "worktree", "add", worktree_path, "-b", branch_name
            ])

            if rc == 0:
                results["variants"].append({
                    "id": i,
                    "branch": branch_name,
                    "path": worktree_path,
                    "status": "created",
                })
            else:
                results["errors"].append({
                    "id": i,
                    "error": err or out,
                })

        return results

    def get_worktree_path(self, experiment_id: str, variant: int) -> str:
        return os.path.join(self.worktrees_dir, f"exp-{experiment_id}-{variant}")

    def run_eval_in_worktree(self, experiment_id: str, variant: int, eval_cmd: str) -> dict:
        """Run an eval command inside a worktree, capture output and timing."""
        worktree_path = self.get_worktree_path(experiment_id, variant)
        if not os.path.isdir(worktree_path):
            return {"variant": variant, "success": False, "error": "Worktree not found"}

        start = time.time()
        try:
            result = subprocess.run(
                eval_cmd,
                shell=True,
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=300,
            )
            elapsed = time.time() - start
            return {
                "variant": variant,
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout[-4000:] if len(result.stdout) > 4000 else result.stdout,
                "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
                "duration_seconds": round(elapsed, 2),
            }
        except subprocess.TimeoutExpired:
            return {
                "variant": variant,
                "success": False,
                "exit_code": -1,
                "error": "Eval command timed out (5 min limit)",
                "duration_seconds": round(time.time() - start, 2),
            }

    def evaluate_all(self, experiment_id: str, eval_cmd: str) -> list[dict]:
        """Run eval in all variant worktrees, return sorted results."""
        # Find all worktrees for this experiment
        results = []
        if not os.path.isdir(self.worktrees_dir):
            return results

        prefix = f"exp-{experiment_id}-"
        variant_dirs = sorted([
            d for d in os.listdir(self.worktrees_dir)
            if d.startswith(prefix) and os.path.isdir(os.path.join(self.worktrees_dir, d))
        ])

        for d in variant_dirs:
            try:
                variant_num = int(d[len(prefix):])
            except ValueError:
                continue
            result = self.run_eval_in_worktree(experiment_id, variant_num, eval_cmd)
            results.append(result)

        # Sort: successful first, then by duration
        results.sort(key=lambda r: (not r.get("success", False), r.get("duration_seconds", 999)))
        return results

    def merge_variant(self, experiment_id: str, variant: int) -> dict:
        """Merge a variant branch into the base branch."""
        branch_name = f"experiment/{experiment_id}/variant-{variant}"

        # Get current branch (should be base)
        base_branch = self._get_current_branch()

        # Make sure we're on the base branch in the main repo
        rc, out, err = self._run_git(["checkout", base_branch])
        if rc != 0:
            return {"success": False, "error": f"Failed to checkout {base_branch}: {err}"}

        # Merge the variant
        rc, out, err = self._run_git(["merge", branch_name, "--no-ff",
                                       "-m", f"Merge experiment {experiment_id} variant {variant}"])
        if rc != 0:
            # Abort merge on conflict
            self._run_git(["merge", "--abort"])
            return {
                "success": False,
                "error": f"Merge conflict: {err}\n{out}",
                "hint": "Resolve conflicts manually or try a different variant.",
            }

        return {"success": True, "message": f"Merged {branch_name} into {base_branch}"}

    def cleanup_experiment(self, experiment_id: str) -> dict:
        """Remove all worktrees and branches for an experiment."""
        removed_worktrees = []
        removed_branches = []
        errors = []

        if not os.path.isdir(self.worktrees_dir):
            return {"removed_worktrees": [], "removed_branches": [], "errors": []}

        prefix = f"exp-{experiment_id}-"
        variant_dirs = [
            d for d in os.listdir(self.worktrees_dir)
            if d.startswith(prefix)
        ]

        for d in variant_dirs:
            worktree_path = os.path.join(self.worktrees_dir, d)
            rc, out, err = self._run_git(["worktree", "remove", worktree_path, "--force"])
            if rc == 0:
                removed_worktrees.append(d)
            else:
                errors.append(f"Failed to remove worktree {d}: {err}")

        # Clean up branches
        rc, out, _ = self._run_git(["branch", "--list", f"experiment/{experiment_id}/*"])
        if rc == 0 and out:
            for branch in out.strip().split("\n"):
                branch = branch.strip().lstrip("* ")
                if not branch:
                    continue
                rc2, _, err2 = self._run_git(["branch", "-D", branch])
                if rc2 == 0:
                    removed_branches.append(branch)
                else:
                    errors.append(f"Failed to delete branch {branch}: {err2}")

        # Remove experiment directory if empty
        exp_dir = os.path.join(self.worktrees_dir, f"exp-{experiment_id}")
        if os.path.isdir(exp_dir):
            try:
                os.rmdir(exp_dir)
            except OSError:
                pass

        return {
            "removed_worktrees": removed_worktrees,
            "removed_branches": removed_branches,
            "errors": errors,
        }

    def list_worktrees(self) -> list[dict]:
        """List all git worktrees."""
        rc, out, _ = self._run_git(["worktree", "list", "--porcelain"])
        if rc != 0:
            return []

        worktrees = []
        current = {}
        for line in out.split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "bare":
                current["bare"] = True
            elif line == "detached":
                current["detached"] = True
            elif not line.strip() and current:
                pass
        if current:
            worktrees.append(current)

        return worktrees

    def get_variant_diff(self, experiment_id: str, variant: int) -> str:
        """Get diff of variant vs base branch."""
        branch_name = f"experiment/{experiment_id}/variant-{variant}"
        base_branch = self._get_current_branch()
        rc, out, err = self._run_git(["diff", f"{base_branch}...{branch_name}"])
        if rc != 0:
            return f"Error getting diff: {err}"
        return out if out else "(no changes)"
