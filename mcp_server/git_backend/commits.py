from pydantic import BaseModel, Field
import subprocess
import re
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from .repo import RepoRef

class CommitTemplate(BaseModel):
    subject: str
    body: Optional[str] = None
    trailers: Optional[Dict[str, str]] = None
    enforce_unique_window: int = 100

def lint_commit_message(template: CommitTemplate, variables: Dict[str, str]) -> Dict[str, Any]:
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
            ["git", "-C", repo.root, "log", f"--oneline", f"-{window}", "--format=%s"],
            capture_output=True, text=True, check=True
        )
        subjects = result.stdout.strip().split('\n')
        return subject not in subjects
    except subprocess.CalledProcessError:
        return True  # Assume unique if check fails

def resolve_collision(subject: str, repo: RepoRef, window: int = 100) -> str:
    base = subject
    counter = 2
    while not check_uniqueness(repo, f"{base} (#{counter})", window):
        counter += 1
    return f"{base} (#{counter})"

def write_and_commit(repo: RepoRef, path: str, content: str, template: CommitTemplate, variables: Dict[str, str], strict_unique: bool = True) -> str:
    """
    Write file, add to git, and commit with template.
    """
    # Write file
    with open(path, 'w') as f:
        f.write(content)
    
    # Git add
    subprocess.run(['git', '-C', repo.root, 'add', path], check=True)
    
    # Render message
    subject = template.subject.format(**variables)
    body = template.body.format(**variables) if template.body else None
    message = subject
    if body:
        message += f"\n\n{body}"
    if template.trailers:
        for k, v in template.trailers.items():
            message += f"\n{k}: {v.format(**variables)}"
    
    # Validate
    is_valid, errors = validate_commit_message(subject, body)
    if not is_valid:
        raise ValueError(f"Invalid commit message: {errors}")
    
    # Check uniqueness
    if not check_uniqueness(repo, subject, template.enforce_unique_window):
        if strict_unique:
            raise ValueError(f"Commit subject not unique: {subject}")
        else:
            message = resolve_collision(subject, repo, template.enforce_unique_window)
    
    # Commit
    result = subprocess.run(['git', '-C', repo.root, 'commit', '-m', message], capture_output=True, text=True, check=True)
    return result.stdout.strip().split()[-1]  # Return commit SHA

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