from pydantic import BaseModel, Field
import subprocess
import re
from pathlib import Path
from .repo import RepoRef

class CommitTemplate(BaseModel):
    subject: str
    body: str = Field(default=None)
    trailers: dict = Field(default=None)
    enforce_unique_window: int = 100

def lint_commit_message(template: CommitTemplate, variables: dict) -> dict:
    errors = []
    subject = template.subject.format(**variables)
    if len(subject) > 72:
        errors.append("Subject exceeds 72 characters")
    required_tokens = ["{op}", "{path}", "{summary}"]
    for token in required_tokens:
        if token not in template.subject:
            errors.append(f"Required token {token} missing in subject")
    return {"ok": len(errors) == 0, "errors": errors}

def check_uniqueness(repo: RepoRef, subject: str, window: int = 100) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", repo.root, "log", f"--oneline", f"-{window}", "--grep", subject],
            capture_output=True, text=True, check=True
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        return True  # Assume unique if check fails

def resolve_collision(subject: str, repo: RepoRef, window: int = 100) -> str:
    base = subject
    counter = 2
    while not check_uniqueness(repo, f"{base} (#{counter})", window):
        counter += 1
    return f"{base} (#{counter})"