import os
import subprocess
from pathlib import Path
from .repo import RepoRef

def enforce_path_under_root(repo: RepoRef, path: str) -> str:
    abs_path = os.path.abspath(os.path.join(repo.root, path))
    if not abs_path.startswith(repo.root):
        raise ValueError(f"Path {path} is outside repo root {repo.root}")
    return abs_path

def check_dirty_tree(repo: RepoRef) -> bool:
    try:
        result = subprocess.run(["git", "-C", repo.root, "status", "--porcelain"], capture_output=True, text=True, check=True)
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return True  # Assume dirty if check fails