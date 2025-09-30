from pathlib import Path
from .commits import CommitTemplate

def load_default_template() -> CommitTemplate:
    template_path = Path(__file__).parent.parent / "assets" / "commit_template.default.txt"
    with open(template_path, 'r') as f:
        content = f.read()
    lines = content.split('\n')
    subject = lines[0]
    body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else None
    return CommitTemplate(subject=subject, body=body)