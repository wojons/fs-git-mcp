#!/usr/bin/env python3
"""
FastMCP server for Git-enforced filesystem operations.
 
This provides a proper MCP server implementation using the FastMCP framework
from the MCP Python SDK, supporting all git_fs, fs_reader, fs_text_replace,
fs_code_diff, and fs_io tool namespaces.
"""
 
from typing import Any, Dict, List, Optional
import sys
import os
from pathlib import Path
 
# Ensure package root is in sys.path for imports when run as script
package_root = Path(__file__).parent.parent.parent
if package_root not in sys.path:
    sys.path.insert(0, str(package_root))
 
from mcp.server.fastmcp import FastMCP
 
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
    ReadIntent,
)
from mcp_server.tools.integrate_text_replace import (
    replace_and_commit as _replace_and_commit,
    batch_replace_and_commit,
)
from mcp_server.tools.integrate_code_diff import (
    preview_diff as _preview_diff,
    apply_patch_and_commit,
)
from mcp_server.tools.integrate_file_system import (
    read_file as _read_file,
    stat_file,
    list_dir,
    make_dir,
)
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.templates import CommitTemplate, load_default_template
from mcp_server.git_backend.commits import lint_commit_message as lint_commit_msg
 
def get_repo_ref(repo: Any) -> RepoRef:
    """Get RepoRef from repo parameter, handling string, dict, or RepoRef."""
    if 'repo' in repo and isinstance(repo['repo'], (str, dict)):
        repo = repo['repo']
    if hasattr(repo, 'root'):
        return repo
    if isinstance(repo, str):
        return RepoRef(root=repo)
    if hasattr(repo, 'get') and callable(repo.get):
        root = repo.get('root') or repo.get('path')
        if root is None:
            raise ValueError('Repo parameter must contain \'root\' or \'path\' key')
        branch = repo.get('branch')
        return RepoRef(root=root, branch=branch)
    raise ValueError('Repo parameter must be string, dict-like, or have .root attribute')
 
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
    repo: Any,
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
    repo_ref = get_repo_ref(repo)
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
    repo: Any,
    path: str,
    history_limit: int = 10
) -> Dict[str, Any]:
    """Read file content with git history."""
    repo_ref = get_repo_ref(repo)
    result = read_with_history_tool(repo_ref, path, history_limit)
    return result
 
@mcp.tool()
def start_staged(
    repo: Any,
    ticket: Optional[str] = None
) -> Dict[str, Any]:
    """Start a staged editing session."""
    repo_ref = get_repo_ref(repo)
    result = start_staged_tool(repo_ref, ticket)
    return result.model_dump()
 
@mcp.tool()
def staged_write(
    session_id: str,
    repo: Any,
    path: str,
    content: str,
    summary: str = "staged edit"
) -> Dict[str, Any]:
    """Write to a staged session."""
    repo_ref = get_repo_ref(repo)
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
    repo: Any,
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
    repo_ref = get_repo_ref(repo)
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
def answer_about_file(
    repo: Any,
    path: str,
    question: str,
    before: int = 3,
    after: int = 3,
    max_spans: int = 20
) -> Dict[str, Any]:
    """Answer questions about a file's content using keyword-based extraction and citations."""
    repo_ref = get_repo_ref(repo)
    
    # Get history for citations
    history_result = read_with_history_tool(repo_ref, path, history_limit=1)
    current_commit = history_result.get('history', [{}])[0] if history_result.get('history') else {}
    
    # Read the file content
    content = _read_file(repo_ref, path)
    if not content:
        return {"answer": "The file is empty or could not be read.", "citations": []}
    
    # Extract keywords from question (simple: words longer than 2 chars, lowercase)
    keywords = [word.lower() for word in question.split() if len(word) > 2 and word.isalpha()]
    if not keywords:
        return {"answer": "No clear keywords found in the question.", "citations": []}
    
    # Split content into lines
    lines = content.splitlines()
    spans = []
    citations = []
    
    for i, line in enumerate(lines):
        if any(keyword in line.lower() for keyword in keywords):
            # Extract context: before and after lines
            start = max(0, i - before)
            end = min(len(lines), i + after + 1)
            span_lines = lines[start:end]
            span = '\n'.join(span_lines)
            spans.append(f"Lines {start+1}-{end}:\n{span}")
            
            # Add citation
            citations.append({
                "sha": current_commit.get('sha', 'unknown'),
                "lines": [f"{start+1}-{end}"]
            })
    
    if spans:
        relevant_content = '\n\n---\n\n'.join(spans[:max_spans])
        answer = f"Based on keywords from the question ('{' '.join(keywords)}'), here are relevant excerpts from the file {path} (current commit {current_commit.get('sha', 'unknown')}):\n\n{relevant_content}"
    else:
        answer = f"No lines containing keywords ('{' '.join(keywords)}') were found in the file {path}."
    
    return {"answer": answer, "citations": citations[:max_spans]}
 
@mcp.tool()
def replace_and_commit(
    repo: Any,
    path: str,
    search: str,
    replace: str,
    regex: bool = False,
    template: Optional[Dict[str, Any]] = None,
    summary: str = "text replacement"
) -> Dict[str, Any]:
    """Replace text in file and commit."""
    repo_ref = get_repo_ref(repo)
    commit_template = to_commit_template(template)
    
    result = _replace_and_commit(
        repo_ref,
        path,
        search,
        replace,
        regex,
        commit_template,
        summary
    )
    return {"commit_sha": result}
 
@mcp.tool()
def preview_diff(
    repo: Any,
    path: str,
    modified_content: str,
    ignore_whitespace: bool = False,
    context_lines: int = 3
) -> Dict[str, Any]:
    """Preview diff between original and modified content."""
    repo_ref = get_repo_ref(repo)
    result = _preview_diff(
        repo_ref,
        path,
        modified_content,
        ignore_whitespace,
        context_lines
    )
    return {"diff": result}
 
@mcp.tool()
def read_file(
    repo: Any,
    path: str
) -> Dict[str, Any]:
    """Read file from repository."""
    repo_ref = get_repo_ref(repo)
    result = _read_file(repo_ref, path)
    return {"content": result}
 
def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")
 
if __name__ == "__main__":
    main()
