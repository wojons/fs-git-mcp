from pydantic import BaseModel
import os
import subprocess
from ..git_backend.repo import RepoRef
from ..git_backend.commits import CommitTemplate, lint_commit_message, check_uniqueness, resolve_collision
from ..git_backend.safety import enforce_path_under_root, check_dirty_tree
from ..git_backend.history import get_file_history
from ..git_backend.staging import StagedSession, start_staged_session, get_preview, finalize_session

class WriteRequest(BaseModel):
    repo: RepoRef
    path: str
    content: str
    template: CommitTemplate
    allow_create: bool = True
    allow_overwrite: bool = True

class WriteResult(BaseModel):
    path: str
    commit_sha: str
    branch: str
    message: str

def write_and_commit(request: WriteRequest) -> WriteResult:
    abs_path = enforce_path_under_root(request.repo, request.path)
    if check_dirty_tree(request.repo) and not request.allow_overwrite:
        raise ValueError("Working tree is dirty and allow_overwrite is false")
    variables = {"op": "write", "path": request.path, "summary": "file write"}
    lint_result = lint_commit_message(request.template, variables)
    if not lint_result["ok"]:
        raise ValueError(f"Commit message lint failed: {lint_result['errors']}")
    subject = request.template.subject.format(**variables)
    if not check_uniqueness(request.repo, subject):
        if request.template.enforce_unique_window:
            raise ValueError(f"Commit subject not unique: {subject}")
        subject = resolve_collision(subject, request.repo)
    with open(abs_path, 'w') as f:
        f.write(request.content)
    subprocess.run(["git", "-C", request.repo.root, "add", request.path], check=True)
    commit_result = subprocess.run(
        ["git", "-C", request.repo.root, "commit", "-m", subject],
        capture_output=True, text=True, check=True
    )
    commit_sha = commit_result.stdout.strip().split()[-1]
    return WriteResult(
        path=request.path,
        commit_sha=commit_sha,
        branch=request.repo.get_current_branch(),
        message=subject
    )

def read_with_history(repo: RepoRef, path: str, history_limit: int = 10) -> dict:
    abs_path = enforce_path_under_root(repo, path)
    history = get_file_history(repo, path, history_limit)
    return {"path": path, "history": history}

# Staged functions would go here, but for brevity, placeholders