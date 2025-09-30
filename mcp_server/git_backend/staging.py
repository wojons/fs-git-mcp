from pydantic import BaseModel, Field
import subprocess
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from .repo import RepoRef
from .commits import write_and_commit, CommitTemplate

class StagedSession(BaseModel):
    id: str
    base_branch: str
    work_branch: str
    started_at: str
    repo: RepoRef

    def write(self, path: str, content: str, template: CommitTemplate, variables: Dict[str, str]):
        return write_and_commit(self.repo, path, content, template, variables)

    def preview(self) -> Dict[str, Any]:
        try:
            log_result = subprocess.run(
                ["git", "-C", self.repo.root, "log", "--oneline", f"{self.base_branch}..{self.work_branch}"],
                capture_output=True, text=True, check=True
            )
            diff_result = subprocess.run(
                ["git", "-C", self.repo.root, "diff", f"{self.base_branch}...{self.work_branch}"],
                capture_output=True, text=True, check=True
            )
            return {
                "diff": diff_result.stdout,
                "commits": [line.strip() for line in log_result.stdout.split('\n') if line.strip()]
            }
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to get preview: {e}")

    def finalize(self, strategy: str = 'merge-ff'):
        if strategy == "merge-ff":
            subprocess.run(["git", "-C", self.repo.root, "checkout", self.base_branch], check=True)
            subprocess.run(["git", "-C", self.repo.root, "merge", "--ff-only", self.work_branch], check=True)
        elif strategy == "rebase-merge":
            subprocess.run(["git", "-C", self.repo.root, "checkout", self.base_branch], check=True)
            subprocess.run(["git", "-C", self.repo.root, "rebase", self.work_branch], check=True)
        # Add other strategies as needed
        merged_sha = subprocess.run(
            ["git", "-C", self.repo.root, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        subprocess.run(["git", "-C", self.repo.root, "branch", "-D", self.work_branch], check=True)
        return merged_sha

    def abort(self):
        subprocess.run(["git", "-C", self.repo.root, "checkout", self.base_branch], check=True)
        subprocess.run(["git", "-C", self.repo.root, "branch", "-D", self.work_branch], check=True)

def start_staged_session(repo: RepoRef, ticket: Optional[str] = None) -> StagedSession:
    base_branch = repo.get_current_branch()
    session_id = f"mcp/{ticket or 'session'}-{str(uuid.uuid4())[:8]}"
    work_branch = f"mcp/staged/{session_id}"
    try:
        subprocess.run(["git", "-C", repo.root, "checkout", "-b", work_branch, base_branch], check=True)
        return StagedSession(
            id=session_id,
            base_branch=base_branch,
            work_branch=work_branch,
            started_at=datetime.utcnow().isoformat(),
            repo=repo
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Failed to create staged session: {e}")

def get_preview(repo: RepoRef, work_branch: str, base_branch: str) -> dict:
    try:
        log_result = subprocess.run(
            ["git", "-C", repo.root, "log", "--oneline", f"{base_branch}..{work_branch}"],
            capture_output=True, text=True, check=True
        )
        diff_result = subprocess.run(
            ["git", "-C", repo.root, "diff", f"{base_branch}...{work_branch}"],
            capture_output=True, text=True, check=True
        )
        return {
            "diff": diff_result.stdout,
            "commits": [line.strip() for line in log_result.stdout.split('\n') if line.strip()]
        }
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Failed to get preview: {e}")

def finalize_session(repo: RepoRef, work_branch: str, base_branch: str, strategy: str) -> str:
    if strategy == "merge-ff":
        subprocess.run(["git", "-C", repo.root, "checkout", base_branch], check=True)
        subprocess.run(["git", "-C", repo.root, "merge", "--ff-only", work_branch], check=True)
    elif strategy == "rebase-merge":
        subprocess.run(["git", "-C", repo.root, "checkout", base_branch], check=True)
        subprocess.run(["git", "-C", repo.root, "rebase", work_branch], check=True)
    # Add other strategies as needed
    merged_sha = subprocess.run(
        ["git", "-C", repo.root, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(["git", "-C", repo.root, "branch", "-D", work_branch], check=True)
    return merged_sha