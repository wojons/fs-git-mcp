from pydantic import BaseModel
import os
import subprocess
from typing import Dict, Any, Optional
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.commits import CommitTemplate, lint_commit_message, check_uniqueness, resolve_collision
from mcp_server.git_backend.safety import enforce_path_under_root, check_dirty_tree, PathAuthorizer, enforce_path_authorization
from mcp_server.git_backend.history import get_file_history, read_with_history
from mcp_server.git_backend.staging import StagedSession, start_staged_session, get_preview, finalize_session, get_session_by_id, remove_session

class WriteRequest(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    
    repo: RepoRef
    path: str
    content: str
    template: CommitTemplate
    allow_create: bool = True
    allow_overwrite: bool = True
    # Variables for template formatting
    op: str = "write"
    summary: str = "file write"
    reason: Optional[str] = None
    ticket: Optional[str] = None
    # Path authorization
    allow_paths: Optional[str] = None
    deny_paths: Optional[str] = None
    path_authorizer: Optional[PathAuthorizer] = None

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
    # Create path authorizer if needed
    authorizer = request.path_authorizer
    if not authorizer and (request.allow_paths or request.deny_paths):
        from mcp_server.git_backend.safety import create_path_authorizer_from_config
        authorizer = create_path_authorizer_from_config(
            repo_root=request.repo.root,
            allow_paths=request.allow_paths,
            deny_paths=request.deny_paths
        )
    
    # Enforce path traversal protection
    abs_path = enforce_path_under_root(request.repo, request.path)
    
    # Enforce path authorization if authorizer is provided
    if authorizer:
        try:
            # Check if the absolute path is authorized
            if not authorizer.is_path_allowed(abs_path):
                denied_summary = authorizer.get_denied_paths_summary()
                allowed_summary = authorizer.get_allowed_paths_summary()
                raise ValueError(
                    f"Path '{request.path}' is not authorized. "
                    f"{denied_summary}. {allowed_summary}"
                )
        except ValueError as e:
            # If path authorization fails, raise the error
            raise ValueError(f"Path authorization failed: {e}")
    
    if check_dirty_tree(request.repo) and not request.allow_overwrite:
        raise ValueError("Working tree is dirty and allow_overwrite is false")
    variables = {"op": request.op, "path": request.path, "summary": request.summary, "reason": request.reason or "", "ticket": request.ticket or "", "files": "", "refs": ""}
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
    from mcp_server.git_backend.staging import get_session_by_id
    abs_path = enforce_path_under_root(request.repo, request.path)
    session = get_session_by_id(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    subprocess.run(["git", "-C", request.repo.root, "checkout", session.work_branch], check=True)
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
    session = get_session_by_id(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    
    preview_data = session.preview()
    return Preview(
        diff=preview_data["diff"],
        files_changed=[],
        commits=[{"sha": "dummy", "subject": commit} for commit in preview_data["commits"]]
    )

def finalize_tool(session_id: str, options: FinalizeOptions) -> Dict[str, str]:
    session = get_session_by_id(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")
    
    merged_sha = session.finalize(options.strategy)
    remove_session(session_id)
    return {"merged_sha": merged_sha, "base_branch": session.base_branch}

def abort_tool(session_id: str) -> Dict[str, str]:
    session = get_session_by_id(session_id)
    if session:
        session.abort()
        remove_session(session_id)
    return {"status": "aborted"}