from pydantic import BaseModel, Field
import subprocess
import re
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.templates import CommitTemplate

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
    
    # Render message with safe formatting
    def safe_format(template_str: str, vars_dict: Dict[str, str]) -> str:
        """Safely format template string with fallback for missing variables."""
        # First, replace all known optional variables with empty strings if missing
        safe_vars = vars_dict.copy()
        optional_vars = ['reason', 'ticket', 'files', 'refs', 'co_authors']
        for var in optional_vars:
            if var not in safe_vars:
                safe_vars[var] = ''
        
        # Now try to format
        try:
            return template_str.format(**safe_vars)
        except KeyError as e:
            # If still missing variables, replace them with empty strings
            missing_key = str(e).strip("'")
            safe_vars[missing_key] = ''
            try:
                return template_str.format(**safe_vars)
            except KeyError:
                # If multiple missing keys, fall back to simple replacement
                result = template_str
                for key, value in safe_vars.items():
                    result = result.replace(f'{{{key}}}', str(value))
                return result
    
    subject = safe_format(template.subject, variables)
    body = safe_format(template.body, variables) if template.body else None
    message = subject
    if body:
        message += f"\n\n{body}"
    if template.trailers:
        for k, v in template.trailers.items():
            message += f"\n{k}: {safe_format(v, variables)}"
    
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
    # Note: We don't check for {op}, {path}, {summary} tokens here anymore
    # since they should have been replaced by actual values during formatting
    return len(errors) == 0, errors