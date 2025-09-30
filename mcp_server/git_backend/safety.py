import os
import subprocess
from pathlib import Path
from typing import Optional
from .repo import RepoRef

def enforce_path_under_root(repo: RepoRef, path: str) -> str:
    abs_path = os.path.abspath(os.path.join(repo.root, path))
    if not abs_path.startswith(repo.root):
        raise ValueError(f"Path {path} is outside repo root {repo.root}")
    return abs_path

def enforce_repo_root(repo_root: str, file_path: str) -> bool:
    """
    Ensure file_path is within repo_root to prevent path traversal.
    """
    try:
        resolved_root = Path(repo_root).resolve()
        resolved_path = Path(file_path).resolve()
        return resolved_path.is_relative_to(resolved_root)
    except (OSError, ValueError):
        return False

def set_git_safe_directory(repo_root: str) -> None:
    """
    Set git safe.directory for the repo root.
    """
    os.environ['GIT_CONFIG_PARAMETERS'] = f"safe.directory={repo_root}"

def check_dirty_tree(repo: RepoRef) -> bool:
    try:
        result = subprocess.run(["git", "-C", repo.root, "status", "--porcelain"], capture_output=True, text=True, check=True)
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return True  # Assume dirty if check fails

def validate_commit_message(subject: str, body: Optional[str] = None) -> tuple[bool, list[str]]:
    """
    Validate commit message: subject <=72 chars, required tokens.
    """
    errors = []
    if len(subject) > 72:
        errors.append("Subject exceeds 72 characters")
    if '{op}' not in subject or '{path}' not in subject or '{summary}' not in subject:
        errors.append("Subject must include {op}, {path}, {summary} tokens")
    return len(errors) == 0, errors