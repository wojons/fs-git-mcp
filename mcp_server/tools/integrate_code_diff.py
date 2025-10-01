import difflib
from typing import Optional
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.commits import write_and_commit, CommitTemplate
from mcp_server.git_backend.safety import enforce_path_under_root
from mcp_server.git_backend.templates import load_default_template


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


def apply_patch_and_commit(repo: RepoRef, path: str, patch: str, template: Optional[CommitTemplate] = None, staged: bool = False, summary: str = "apply patch") -> str:
    """
    Apply patch and commit.
    """
    from mcp_server.git_backend.templates import load_default_template
    
    abs_path = enforce_path_under_root(repo, path)
    with open(abs_path, 'r') as f:
        content = f.read()
    
    # Parse unified diff format and apply changes
    lines: list[str] = content.split('\n')
    new_lines_list: list[str] = lines.copy()
    
    # Simple unified diff parser
    patch_lines = patch.strip().split('\n')
    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]
        if line.startswith('@@'):
            # Parse hunk header
            # Format: @@ -old_start,old_lines +new_start,new_lines @@
            import re
            hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if hunk_match:
                old_start = int(hunk_match.group(1))
                old_lines = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                new_start = int(hunk_match.group(3))
                new_lines_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
                
                # Apply hunk
                i += 1
                old_idx = old_start - 1  # Convert to 0-based
                new_idx = new_start - 1
                
                while i < len(patch_lines) and not patch_lines[i].startswith('@@') and not patch_lines[i].startswith('---') and not patch_lines[i].startswith('+++'):
                    patch_line = patch_lines[i]
                    if patch_line.startswith(' '):
                        # Context line - should match
                        if old_idx < len(new_lines_list) and new_lines_list[old_idx] != patch_line[1:]:
                            raise ValueError(f"Context mismatch at line {old_idx + 1}")
                        old_idx += 1
                        new_idx += 1
                    elif patch_line.startswith('-'):
                        # Removal line
                        if old_idx < len(new_lines_list):
                            new_lines_list.pop(old_idx)
                        new_idx += 1
                    elif patch_line.startswith('+'):
                        # Addition line
                        new_lines_list.insert(old_idx, patch_line[1:])
                        old_idx += 1
                        new_idx += 1
                    i += 1
                continue
        i += 1
    
    new_content = '\n'.join(new_lines_list)
    
    variables = {'op': 'patch', 'path': path, 'summary': summary}
    if template is None:
        template = load_default_template()
    sha = write_and_commit(repo, abs_path, new_content, template, variables)
    return sha