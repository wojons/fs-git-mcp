import re
from typing import Optional
from ..git_backend.repo import RepoRef
from ..git_backend.commits import write_and_commit, CommitTemplate
from ..git_backend.safety import enforce_path_under_root


def replace_and_commit(repo: RepoRef, path: str, search: str, replace: str, regex: bool = False, template: Optional[CommitTemplate] = None) -> str:
    if template is None:
        from ..git_backend.templates import load_default_template
        template = load_default_template()
    """
    Replace text and commit.
    """
    abs_path = enforce_path_under_root(repo, path)
    with open(abs_path, 'r') as f:
        content = f.read()
    
    if regex:
        new_content = re.sub(search, replace, content)
    else:
        new_content = content.replace(search, replace)
    
    variables = {'op': 'replace', 'path': path, 'summary': 'text replace'}
    sha = write_and_commit(repo, abs_path, new_content, template, variables)
    return sha


def batch_replace_and_commit(repo: RepoRef, replacements: list[dict], template: Optional[CommitTemplate] = None) -> list[str]:
    """
    Batch replace and commit per file.
    """
    shas = []
    for rep in replacements:
        sha = replace_and_commit(repo, rep['path'], rep['search'], rep['replace'], rep.get('regex', False), template)
        shas.append(sha)
    return shas