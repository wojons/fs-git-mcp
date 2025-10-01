#!/usr/bin/env python3
"""
FastMCP server for Git-enforced filesystem operations.

This provides a proper MCP server implementation using the FastMCP framework
from the MCP Python SDK, supporting all git_fs, fs_reader, fs_text_replace,
fs_code_diff, and fs_io tool namespaces.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
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

# Create low-level server
server = Server("fs-git")

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

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="write_and_commit",
            description="Write a file and create an atomic git commit with templated message",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "template": {"type": "object"},
                    "op": {"type": "string"},
                    "summary": {"type": "string"},
                    "reason": {"type": "string"},
                    "ticket": {"type": "string"},
                    "allow_create": {"type": "boolean"},
                    "allow_overwrite": {"type": "boolean"}
                },
                "required": ["repo", "path", "content"]
            }
        ),
        types.Tool(
            name="read_with_history",
            description="Read file content with git history",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "history_limit": {"type": "integer"}
                },
                "required": ["repo", "path"]
            }
        ),
        types.Tool(
            name="start_staged",
            description="Start a staged editing session",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "ticket": {"type": "string"}
                },
                "required": ["repo"]
            }
        ),
        types.Tool(
            name="staged_write",
            description="Write to a staged session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "summary": {"type": "string"}
                },
                "required": ["session_id", "repo", "path", "content"]
            }
        ),
        types.Tool(
            name="staged_preview",
            description="Preview staged changes",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"}
                },
                "required": ["session_id"]
            }
        ),
        types.Tool(
            name="finalize_staged",
            description="Finalize a staged session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["merge-ff", "merge-no-ff", "rebase-merge", "squash-merge"]},
                    "delete_work_branch": {"type": "boolean"}
                },
                "required": ["session_id"]
            }
        ),
        types.Tool(
            name="abort_staged",
            description="Abort a staged session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"}
                },
                "required": ["session_id"]
            }
        ),
        types.Tool(
            name="extract",
            description="Extract relevant spans from a file based on query",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "query": {"type": "string"},
                    "regex": {"type": "boolean"},
                    "before": {"type": "integer"},
                    "after": {"type": "integer"},
                    "max_spans": {"type": "integer"},
                    "include_content": {"type": "boolean"},
                    "history_limit": {"type": "integer"}
                },
                "required": ["repo", "path"]
            }
        ),
        types.Tool(
            name="answer_about_file",
            description="Answer questions about a file's content",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "question": {"type": "string"},
                    "before": {"type": "integer"},
                    "after": {"type": "integer"},
                    "max_spans": {"type": "integer"}
                },
                "required": ["repo", "path", "question"]
            }
        ),
        types.Tool(
            name="replace_and_commit",
            description="Replace text in file and commit",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "search": {"type": "string"},
                    "replace": {"type": "string"},
                    "regex": {"type": "boolean"},
                    "template": {"type": "object"},
                    "summary": {"type": "string"}
                },
                "required": ["repo", "path", "search", "replace"]
            }
        ),
        types.Tool(
            name="preview_diff",
            description="Preview diff between original and modified content",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"},
                    "modified_content": {"type": "string"},
                    "ignore_whitespace": {"type": "boolean"},
                    "context_lines": {"type": "integer"}
                },
                "required": ["repo", "path", "modified_content"]
            }
        ),
        types.Tool(
            name="read_file",
            description="Read file from repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "object", "properties": {"root": {"type": "string"}, "branch": {"type": "string"}}, "required": ["root"]},
                    "path": {"type": "string"}
                },
                "required": ["repo", "path"]
            }
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls."""
    try:
        if name == "write_and_commit":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            template = to_commit_template(arguments.get("template"))
            
            request = WriteRequest(
                repo=repo_ref,
                path=arguments["path"],
                content=arguments["content"],
                template=template,
                op=arguments.get("op", "write"),
                summary=arguments.get("summary", "file write"),
                reason=arguments.get("reason"),
                ticket=arguments.get("ticket"),
                allow_create=arguments.get("allow_create", True),
                allow_overwrite=arguments.get("allow_overwrite", True)
            )
            
            result = write_and_commit_tool(request)
            return [types.TextContent(type="text", text=json.dumps(result.model_dump()))]
        
        elif name == "read_with_history":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            result = read_with_history_tool(repo_ref, arguments["path"], arguments.get("history_limit", 10))
            return [types.TextContent(type="text", text=json.dumps(result))]
        
        elif name == "start_staged":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            result = start_staged_tool(repo_ref, arguments.get("ticket"))
            return [types.TextContent(type="text", text=json.dumps(result.model_dump()))]
        
        elif name == "staged_write":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            template = load_default_template()
            
            request = WriteRequest(
                repo=repo_ref,
                path=arguments["path"],
                content=arguments["content"],
                template=template,
                op="staged",
                summary=arguments.get("summary", "staged edit")
            )
            
            result = staged_write_tool(arguments["session_id"], request)
            return [types.TextContent(type="text", text=json.dumps(result.model_dump()))]
        
        elif name == "staged_preview":
            result = staged_preview_tool(arguments["session_id"])
            return [types.TextContent(type="text", text=json.dumps(result.model_dump()))]
        
        elif name == "finalize_staged":
            finalize_opts = FinalizeOptions(
                strategy=arguments.get("strategy", "merge-ff"),
                delete_work_branch=arguments.get("delete_work_branch", True)
            )
            result = finalize_tool(arguments["session_id"], finalize_opts)
            return [types.TextContent(type="text", text=json.dumps(result))]
        
        elif name == "abort_staged":
            result = abort_tool(arguments["session_id"])
            return [types.TextContent(type="text", text=json.dumps(result))]
        
        elif name == "extract":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            read_intent = ReadIntent(
                path=arguments["path"],
                query=arguments.get("query"),
                regex=arguments.get("regex", False),
                before=arguments.get("before", 3),
                after=arguments.get("after", 3),
                max_spans=arguments.get("max_spans", 20),
                include_content=arguments.get("include_content", False),
                history_limit=arguments.get("history_limit", 10)
            )
            
            result = extract_tool(repo_ref, read_intent)
            return [types.TextContent(type="text", text=json.dumps(result.model_dump()))]
        
        elif name == "answer_about_file":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            result = answer_about_file_tool(
                repo_ref,
                arguments["path"],
                arguments["question"],
                arguments.get("before", 3),
                arguments.get("after", 3),
                arguments.get("max_spans", 20)
            )
            return [types.TextContent(type="text", text=json.dumps(result))]
        
        elif name == "replace_and_commit":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            template = to_commit_template(arguments.get("template"))
            
            result = replace_and_commit(
                repo_ref,
                arguments["path"],
                arguments["search"],
                arguments["replace"],
                arguments.get("regex", False),
                template,
                arguments.get("summary", "text replacement")
            )
            return [types.TextContent(type="text", text=json.dumps({"commit_sha": result}))]
        
        elif name == "preview_diff":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            result = preview_diff(
                repo_ref,
                arguments["path"],
                arguments["modified_content"],
                arguments.get("ignore_whitespace", False),
                arguments.get("context_lines", 3)
            )
            return [types.TextContent(type="text", text=json.dumps({"diff": result}))]
        
        elif name == "read_file":
            repo_ref = RepoRef(root=arguments["repo"]["root"], branch=arguments["repo"].get("branch"))
            result = read_file(repo_ref, arguments["path"])
            return [types.TextContent(type="text", text=json.dumps({"content": result}))]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}))]

async def run():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="fs-git",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def main():
    """Run the MCP server."""
    asyncio.run(run())

if __name__ == "__main__":
    main()