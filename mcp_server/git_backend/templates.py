from pathlib import Path
from pydantic import BaseModel
from typing import Optional, Dict
import re
import subprocess

class CommitTemplate(BaseModel):
    subject: str
    body: Optional[str] = None
    trailers: Optional[Dict[str, str]] = None
    enforce_unique_window: int = 100

def load_default_template() -> CommitTemplate:
    template_path = Path(__file__).parent.parent / "assets" / "commit_template.default.txt"
    with open(template_path, 'r') as f:
        content = f.read()
    lines = content.split('\n')
    subject = lines[0]
    body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else None
    return CommitTemplate(subject=subject, body=body)

def render_template(template: CommitTemplate, variables: Dict[str, str]) -> str:
    """
    Render the template with variables.
    """
    subject = template.subject.format(**variables)
    body = template.body.format(**variables) if template.body else None
    message = subject
    if body:
        message += f"\n\n{body}"
    if template.trailers:
        for k, v in template.trailers.items():
            message += f"\n{k}: {v.format(**variables)}"
    return message

def check_uniqueness(repo_root: str, subject: str, window: int = 100) -> bool:
    """
    Check if subject is unique in last N commits.
    """
    try:
        result = subprocess.run(
            ['git', 'log', f'--oneline', f'-{window}', '--format=%s'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True
        )
        subjects = result.stdout.strip().split('\n')
        return subject not in subjects
    except subprocess.CalledProcessError:
        return True  # Assume unique if check fails

def resolve_collision(subject: str) -> str:
    """
    Append (#2) style suffix on collision.
    """
    match = re.search(r' \(#\d+\)$', subject)
    if match:
        num = int(match.group(0)[3:-1]) + 1
        return re.sub(r' \(#\d+\)$', f' (#{num})', subject)
    else:
        return f"{subject} (#2)"