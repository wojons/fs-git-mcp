import difflib
from typing import Optional
from ..git_backend.repo import RepoRef
from ..git_backend.commits import write_and_commit, CommitTemplate
from ..git_backend.safety import enforce_path_under_root
from ..git_backend.templates import load_default_template


def preview_diff(repo: RepoRef, path: str, modified_content: str, ignore_whitespace: bool = False, context_lines: int = 3) -> str:
    """
    Preview diff for modified content.
    """
    abs_path = enforce_path_under_root(repo, path)
    with open(abs_path, 'r') as f:
        original = f.read()
    if ignore_whitespace:
        original = '\n'.join(line.rstrip() for line in original.split('\n'))
        modified_content = '\n'.join(line.rstrip() for line in modified_content.split('\n'))
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified_content.splitlines(keepends=True),
        fromfile=f'a/{path}',
        tofile=f'b/{path}',
        lineterm='',
        n=context_lines
    )
    return '\n'.join(diff)


def apply_patch_and_commit(repo: RepoRef, path: str, patch: str, template: CommitTemplate = None, staged: bool = False, summary: str = "apply patch") -> str:
    """
    Apply patch and commit.
    """
    from ..git_backend.templates import load_default_template
    
    abs_path = enforce_path_under_root(repo, path)
    with open(abs_path, 'r') as f:
        content = f.read()
    
    # Simple patch application (for demo, use a proper library in production)
    lines = content.split('\n')
    # Placeholder for patch application
    new_content = content  # For now, no change
    
    variables = {'op': 'patch', 'path': path, 'summary': summary}
    if template is None:
        template = load_default_template()
    sha = write_and_commit(repo, abs_path, new_content, template, variables)
    return sha