from typing import Optional
from pathlib import Path
from pydantic import BaseModel, Field
import subprocess
import os

class RepoRef(BaseModel):
    root: str
    branch: Optional[str] = Field(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        self.root = os.path.abspath(self.root)
        if not os.path.isdir(self.root):
            raise ValueError(f"Repo root {self.root} is not a directory")
        # Enforce git safe.directory
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", self.root], check=True)
        if not self._is_git_repo():
            raise ValueError(f"{self.root} is not a git repository")

    def _is_git_repo(self) -> bool:
        try:
            subprocess.run(["git", "-C", self.root, "rev-parse", "--git-dir"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def get_current_branch(self) -> str:
        result = subprocess.run(["git", "-C", self.root, "branch", "--show-current"], capture_output=True, text=True, check=True)
        return result.stdout.strip()