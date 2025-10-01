#!/usr/bin/env python3
"""
FastMCP server for Git-enforced filesystem operations.

This provides a proper MCP server implementation using the FastMCP framework
from the MCP Python SDK, supporting all git_fs, fs_reader, fs_text_replace,
fs_code_diff, and fs_io tool namespaces.
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

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
    WriteResult,
    FinalizeOptions,
)
from mcp_server.tools.reader import (
    extract_tool,
    answer_about_file_tool,
    ReadIntent,
)
from mcp_server.tools.integrate_text_replace import (
    replace_and_commit,
    batch_replace_and_commit,
)
from mcp_server.tools.integrate_code_diff import (
    preview_diff,
    apply_patch_and_commit,
)
from mcp_server.tools.integrate_file_system import (
    read_file,
    stat_file,
    list_dir,
    make_dir,
)
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.templates import CommitTemplate, load_default_template
from mcp_server.git_backend.commits import lint_commit_message as lint_commit_msg

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

# Git FS Tools
@mcp.tool()
def write_and_commit(repo: Dict[str, Any], path: str, content: str, template: Optional[Dict[str, Any]] = None, op: str = "write", summary: str = "file write", reason: Optional[str] = None, ticket: Optional[str] = None, allow_create: bool = True, allow_overwrite: bool = True) -> Dict[str, Any]:
    """Write a file and create an atomic git commit with templated message."""
    # Convert to internal models
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    commit_template = to_commit_template(template)
    
    write_request = WriteRequest(
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
    
    result = write_and_commit_tool(write_request)
    return result.model_dump()

@mcp.tool()
def read_with_history(repo: Dict[str, Any], path: str, history_limit: int = 10) -> Dict[str, Any]:
    """Read file content with git history."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = read_with_history_tool(repo_ref, path, history_limit)
    return result

@mcp.tool()
def start_staged(repo: Dict[str, Any], ticket: Optional[str] = None) -> Dict[str, Any]:
    """Start a staged editing session."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = start_staged_tool(repo_ref, ticket)
    return result.model_dump()

@mcp.tool()
def staged_write(session_id: str, repo: Dict[str, Any], path: str, content: str, summary: str = "staged edit") -> Dict[str, Any]:
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
def finalize_staged(session_id: str, strategy: str = "merge-ff", delete_work_branch: bool = True) -> Dict[str, Any]:
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
def lint_commit_message(template: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
    """Validate commit message template."""
    commit_template = to_commit_template(template)
    result = lint_commit_msg(commit_template, variables)
    return result

# Reader Tools
@mcp.tool()
def extract(repo: Dict[str, Any], path: str, query: Optional[str] = None, regex: bool = False, before: int = 3, after: int = 3, max_spans: int = 20, include_content: bool = False, history_limit: int = 10) -> Dict[str, Any]:
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
def answer_about_file(repo: Dict[str, Any], path: str, question: str, before: int = 3, after: int = 3, max_spans: int = 20) -> Dict[str, Any]:
    """Answer questions about a file's content."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = answer_about_file_tool(repo_ref, path, question, before, after, max_spans)
    return result

# Text Replace Tools
@mcp.tool()
def replace_and_commit_func(repo: Dict[str, Any], path: str, search: str, replace: str, regex: bool = False, template: Optional[Dict[str, Any]] = None, summary: str = "text replacement") -> Dict[str, Any]:
    """Replace text in file and commit."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    commit_template = to_commit_template(template)
    
    result = replace_and_commit(repo_ref, path, search, replace, regex, commit_template, summary)
    return {"commit_sha": result}

@mcp.tool()
def batch_replace_and_commit_func(repo: Dict[str, Any], replacements: List[Dict[str, Any]], template: Optional[Dict[str, Any]] = None, summary: str = "batch text replacement") -> Dict[str, Any]:
    """Replace multiple patterns and commit."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    commit_template = to_commit_template(template)
    
    result = batch_replace_and_commit(repo_ref, replacements, commit_template, summary)
    return {"commit_shas": result}

# Code Diff Tools
@mcp.tool()
def preview_diff_func(repo: Dict[str, Any], path: str, modified_content: str, ignore_whitespace: bool = False, context_lines: int = 3) -> Dict[str, Any]:
    """Preview diff between original and modified content."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = preview_diff(repo_ref, path, modified_content, ignore_whitespace, context_lines)
    return {"diff": result}

@mcp.tool()
def apply_patch_and_commit_func(repo: Dict[str, Any], path: str, patch: str, template: Optional[Dict[str, Any]] = None, summary: str = "apply patch") -> Dict[str, Any]:
    """Apply patch and commit."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    commit_template = to_commit_template(template)
    
    result = apply_patch_and_commit(repo_ref, path, patch, commit_template, False, summary)
    return {"commit_sha": result}

# File I/O Tools
@mcp.tool()
def read_file_func(repo: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Read file from repository."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = read_file(repo_ref, path)
    return {"content": result}

@mcp.tool()
def stat_file_func(repo: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Get file statistics."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = stat_file(repo_ref, path)
    return result

@mcp.tool()
def list_dir_func(repo: Dict[str, Any], path: str, recursive: bool = False) -> Dict[str, Any]:
    """List directory contents."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = list_dir(repo_ref, path, recursive)
    return {"files": result}

@mcp.tool()
def make_dir_func(repo: Dict[str, Any], path: str, recursive: bool = False) -> Dict[str, Any]:
    """Create directory."""
    repo_ref = RepoRef(root=repo["root"], branch=repo.get("branch"))
    result = make_dir(repo_ref, path, recursive)
    return result

def main():
    """Run the MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()