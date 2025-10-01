#!/usr/bin/env python3
"""
Standalone FastMCP server for Git-enforced filesystem operations.
"""

import sys
import os
from pathlib import Path

# Add the mcp_server directory to the path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, Optional

# Import our existing tools
from mcp_server.tools.git_fs import (
    write_and_commit_tool,
    read_with_history_tool,
    start_staged_tool,
    staged_write_tool,
    staged_preview_tool,
    finalize_tool,
    abort_tool,
    WriteRequest,
    FinalizeOptions,
)
from mcp_server.tools.reader import (
    extract_tool,
    answer_about_file_tool,
    ReadIntent,
)
from mcp_server.tools.integrate_text_replace import replace_and_commit
from mcp_server.tools.integrate_code_diff import preview_diff
from mcp_server.tools.integrate_file_system import read_file
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.templates import CommitTemplate, load_default_template

# Create FastMCP server
mcp = FastMCP("fs-git")

# Helper function to convert dict to CommitTemplate
def to_commit_template(template_dict: Optional[Dict[str, Any]], default_subject: str = "[{op}] {path} – {summary}") -> CommitTemplate:
    """Convert dict to CommitTemplate."""
    if template_dict is None:
        return CommitTemplate(subject=default_subject)
    
    return CommitTemplate(
        subject=template_dict.get("subject", default_subject),
        body=template_dict.get("body"),
        trailers=template_dict.get("trailers"),
        enforce_unique_window=template_dict.get("enforce_unique_window", 100)
    )

@mcp.tool()
def write_and_commit(
    repo: Dict[str, Any],
    path: str,
    content: str,
    template: Optional[Dict[str, Any]] = None,
    op: str = "write",
    summary: str = "file write",
    reason: Optional[str] = None,
    ticket: Optional[str] = None,
    allow_create: bool = True,
    allow_overwrite: bool = True
) -> Dict[str, Any]:
    """Write a file and create an atomic git commit with templated message."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    commit_template = to_commit_template(template)
    
    request = WriteRequest(
        repo=repo_ref,
        path=path,
        content=content,
        template=commit_template,
        op=op,
        summary=summary,
        reason=reason,
        ticket=ticket,
        allow_create=allow_create,
        allow_overwrite=allow_overwrite
    )
    
    result = write_and_commit_tool(request)
    return result.model_dump()

@mcp.tool()
def read_with_history(
    repo: Dict[str, Any],
    path: str,
    history_limit: int = 10
) -> Dict[str, Any]:
    """Read file content with git history."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = read_with_history_tool(repo_ref, path, history_limit)
    return result

@mcp.tool()
def start_staged(
    repo: Dict[str, Any],
    ticket: Optional[str] = None
) -> Dict[str, Any]:
    """Start a staged editing session."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = start_staged_tool(repo_ref, ticket)
    return result.model_dump()

@mcp.tool()
def staged_write(
    session_id: str,
    repo: Dict[str, Any],
    path: str,
    content: str,
    summary: str = "staged edit"
) -> Dict[str, Any]:
    """Write to a staged session."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    template = load_default_template()
    
    request = WriteRequest(
        repo=repo_ref,
        path=path,
        content=content,
        template=template,
        op="staged",
        summary=summary
    )
    
    result = staged_write_tool(session_id, request)
    return result.model_dump()

@mcp.tool()
def staged_preview(session_id: str) -> Dict[str, Any]:
    """Preview staged changes."""
    result = staged_preview_tool(session_id)
    return result.model_dump()

@mcp.tool()
def finalize_staged(
    session_id: str,
    strategy: str = "merge-ff",
    delete_work_branch: bool = True
) -> Dict[str, Any]:
    """Finalize a staged session."""
    finalize_opts = FinalizeOptions(
        strategy=strategy,
        delete_work_branch=delete_work_branch
    )
    result = finalize_tool(session_id, finalize_opts)
    return result

@mcp.tool()
def abort_staged(session_id: str) -> Dict[str, Any]:
    """Abort a staged session."""
    result = abort_tool(session_id)
    return result

@mcp.tool()
def extract(
    repo: Dict[str, Any],
    path: str,
    query: Optional[str] = None,
    regex: bool = False,
    before: int = 3,
    after: int = 3,
    max_spans: int = 20,
    include_content: bool = False,
    history_limit: int = 10
) -> Dict[str, Any]:
    """Extract relevant spans from a file based on query."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    read_intent = ReadIntent(
        path=path,
        query=query,
        regex=regex,
        before=before,
        after=after,
        max_spans=max_spans,
        include_content=include_content,
        history_limit=history_limit
    )
    
    result = extract_tool(repo_ref, read_intent)
    return result.model_dump()

@mcp.tool()
def read_file(
    repo: Dict[str, Any],
    path: str
) -> Dict[str, Any]:
    """Read file from repository."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = read_file(repo_ref, path)
    return {"content": result}

@mcp.tool()
def test_add(a: int, b: int) -> int:
    """Simple test tool that adds two numbers."""
    return a + b

if __name__ == "__main__":
    mcp.run()