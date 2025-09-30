from pydantic import BaseModel
import os
import subprocess
from typing import Dict, Any, Optional
from ..git_backend.repo import RepoRef
from ..git_backend.commits import CommitTemplate, lint_commit_message, check_uniqueness, resolve_collision
from ..git_backend.safety import enforce_path_under_root, check_dirty_tree
from ..git_backend.history import get_file_history, read_with_history
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

class StagedSessionModel(BaseModel):
    id: str
    base_branch: str
    work_branch: str
    started_at: str

class Preview(BaseModel):
    diff: str
    files_changed: list[str]
    commits: list[Dict[str, str]]

class FinalizeOptions(BaseModel):
    strategy: str = "merge-ff"
    delete_work_branch: bool = True

def write_and_commit_tool(request: WriteRequest) -> WriteResult:
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

def read_with_history_tool(repo: RepoRef, path: str, history_limit: int = 10) -> Dict[str, Any]:
    abs_path = enforce_path_under_root(repo, path)
    return read_with_history(repo, path, history_limit)

def start_staged_tool(repo: RepoRef, ticket: Optional[str] = None, template: Optional[CommitTemplate] = None) -> StagedSessionModel:
    session = start_staged_session(repo, ticket)
    return StagedSessionModel(
        id=session.id,
        base_branch=session.base_branch,
        work_branch=session.work_branch,
        started_at=session.started_at
    )

def staged_write_tool(session_id: str, request: WriteRequest) -> WriteResult:
    # For staged, we need to switch to work branch first
    abs_path = enforce_path_under_root(request.repo, request.path)
    subprocess.run(["git", "-C", request.repo.root, "checkout", "work_branch"], check=True)  # Placeholder
    variables = {"op": "staged", "path": request.path, "summary": "staged write"}
    lint_result = lint_commit_message(request.template, variables)
    if not lint_result["ok"]:
        raise ValueError(f"Commit message lint failed: {lint_result['errors']}")
    subject = request.template.subject.format(**variables)
    if not check_uniqueness(request.repo, subject):
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

def staged_preview_tool(session_id: str) -> Preview:
    # Retrieve session and get preview
    return Preview(diff="", files_changed=[], commits=[])

def finalize_tool(session_id: str, options: FinalizeOptions) -> Dict[str, str]:
    merged_sha = finalize_session(None, "", "", options.strategy)
    return {"merged_sha": merged_sha, "base_branch": "main"}

def abort_tool(session_id: str) -> Dict[str, str]:
    return {"status": "aborted"}