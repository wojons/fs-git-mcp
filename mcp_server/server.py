#!/usr/bin/env python3
"""
Proper MCP Server implementation using the Python SDK.

This server implements the full MCP protocol for Git-enforced filesystem operations.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional

import mcp
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

# Import our tools and types
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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server instance
server = Server("fs-git-mcp")

# Tool definitions
TOOLS = [
    Tool(
        name="write_and_commit",
        description="Write a file and create an atomic git commit with templated message",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "content": {"type": "string", "description": "File content to write"},
                "template": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Commit message subject template"},
                        "body": {"type": "string", "description": "Commit message body template"},
                        "trailers": {"type": "object", "description": "Commit message trailers"},
                        "enforce_unique_window": {"type": "integer", "description": "Number of commits to check for uniqueness"}
                    }
                },
                "op": {"type": "string", "description": "Operation type for template"},
                "summary": {"type": "string", "description": "Summary for template"},
                "reason": {"type": "string", "description": "Reason for change"},
                "ticket": {"type": "string", "description": "Ticket identifier"},
                "allow_create": {"type": "boolean", "description": "Allow file creation"},
                "allow_overwrite": {"type": "boolean", "description": "Allow file overwrite"}
            },
            "required": ["repo", "path", "content"]
        }
    ),
    Tool(
        name="read_with_history",
        description="Read file content with git history",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "history_limit": {"type": "integer", "description": "Number of history entries to return"}
            },
            "required": ["repo", "path"]
        }
    ),
    Tool(
        name="start_staged",
        description="Start a staged editing session",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "ticket": {"type": "string", "description": "Ticket identifier for session"}
            },
            "required": ["repo"]
        }
    ),
    Tool(
        name="staged_write",
        description="Write to a staged session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Staged session ID"},
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "content": {"type": "string", "description": "File content to write"},
                "summary": {"type": "string", "description": "Summary for commit message"}
            },
            "required": ["session_id", "repo", "path", "content"]
        }
    ),
    Tool(
        name="staged_preview",
        description="Preview staged changes",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Staged session ID"}
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="finalize_staged",
        description="Finalize a staged session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Staged session ID"},
                "strategy": {
                    "type": "string",
                    "enum": ["merge-ff", "merge-no-ff", "rebase-merge", "squash-merge"],
                    "description": "Merge strategy"
                },
                "delete_work_branch": {"type": "boolean", "description": "Delete work branch after finalization"}
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="abort_staged",
        description="Abort a staged session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Staged session ID"}
            },
            "required": ["session_id"]
        }
    ),
    Tool(
        name="extract",
        description="Extract relevant spans from a file based on query",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "query": {"type": "string", "description": "Search query"},
                "regex": {"type": "boolean", "description": "Use regex for query"},
                "before": {"type": "integer", "description": "Lines of context before match"},
                "after": {"type": "integer", "description": "Lines of context after match"},
                "max_spans": {"type": "integer", "description": "Maximum number of spans to return"},
                "include_content": {"type": "boolean", "description": "Include full file content"},
                "history_limit": {"type": "integer", "description": "Number of history entries to return"}
            },
            "required": ["repo", "path", "query"]
        }
    ),
    Tool(
        name="answer_about_file",
        description="Answer questions about a file's content",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "question": {"type": "string", "description": "Question to answer"},
                "before": {"type": "integer", "description": "Lines of context before match"},
                "after": {"type": "integer", "description": "Lines of context after match"},
                "max_spans": {"type": "integer", "description": "Maximum number of spans to return"}
            },
            "required": ["repo", "path", "question"]
        }
    ),
    Tool(
        name="replace_and_commit",
        description="Replace text in file and commit",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "search": {"type": "string", "description": "Text to search for"},
                "replace": {"type": "string", "description": "Replacement text"},
                "regex": {"type": "boolean", "description": "Use regex for search"},
                "template": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Commit message subject template"},
                        "body": {"type": "string", "description": "Commit message body template"},
                        "trailers": {"type": "object", "description": "Commit message trailers"},
                        "enforce_unique_window": {"type": "integer", "description": "Number of commits to check for uniqueness"}
                    }
                },
                "summary": {"type": "string", "description": "Summary for commit message"}
            },
            "required": ["repo", "path", "search", "replace"]
        }
    ),
    Tool(
        name="batch_replace_and_commit",
        description="Replace multiple patterns and commit",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "replacements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to file"},
                            "search": {"type": "string", "description": "Text to search for"},
                            "replace": {"type": "string", "description": "Replacement text"},
                            "regex": {"type": "boolean", "description": "Use regex for search"}
                        },
                        "required": ["path", "search", "replace"]
                    }
                },
                "template": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Commit message subject template"},
                        "body": {"type": "string", "description": "Commit message body template"},
                        "trailers": {"type": "object", "description": "Commit message trailers"},
                        "enforce_unique_window": {"type": "integer", "description": "Number of commits to check for uniqueness"}
                    }
                },
                "summary": {"type": "string", "description": "Summary for commit message"}
            },
            "required": ["repo", "replacements"]
        }
    ),
    Tool(
        name="preview_diff",
        description="Preview diff between original and modified content",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "modified_content": {"type": "string", "description": "Modified file content"},
                "ignore_whitespace": {"type": "boolean", "description": "Ignore whitespace changes"},
                "context_lines": {"type": "integer", "description": "Number of context lines"}
            },
            "required": ["repo", "path", "modified_content"]
        }
    ),
    Tool(
        name="apply_patch_and_commit",
        description="Apply patch and commit",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"},
                "patch": {"type": "string", "description": "Patch to apply"},
                "template": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Commit message subject template"},
                        "body": {"type": "string", "description": "Commit message body template"},
                        "trailers": {"type": "object", "description": "Commit message trailers"},
                        "enforce_unique_window": {"type": "integer", "description": "Number of commits to check for uniqueness"}
                    }
                },
                "summary": {"type": "string", "description": "Summary for commit message"}
            },
            "required": ["repo", "path", "patch"]
        }
    ),
    Tool(
        name="read_file",
        description="Read file from repository",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"}
            },
            "required": ["repo", "path"]
        }
    ),
    Tool(
        name="stat_file",
        description="Get file statistics",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to file within repository"}
            },
            "required": ["repo", "path"]
        }
    ),
    Tool(
        name="list_dir",
        description="List directory contents",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to directory within repository"},
                "recursive": {"type": "boolean", "description": "List recursively"}
            },
            "required": ["repo", "path"]
        }
    ),
    Tool(
        name="make_dir",
        description="Create directory",
        inputSchema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Path to git repository root"},
                "path": {"type": "string", "description": "Path to directory within repository"},
                "recursive": {"type": "boolean", "description": "Create parent directories"}
            },
            "required": ["repo", "path"]
        }
    ),
    Tool(
        name="lint_commit_message",
        description="Validate commit message template",
        inputSchema={
            "type": "object",
            "properties": {
                "template": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Commit message subject template"},
                        "body": {"type": "string", "description": "Commit message body template"},
                        "trailers": {"type": "object", "description": "Commit message trailers"},
                        "enforce_unique_window": {"type": "integer", "description": "Number of commits to check for uniqueness"}
                    },
                    "required": ["subject"]
                },
                "variables": {
                    "type": "object",
                    "description": "Template variables for validation"
                }
            },
            "required": ["template", "variables"]
        }
    ),
]

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return TOOLS

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "write_and_commit":
            repo_ref = RepoRef(root=arguments["repo"])
            template_data = arguments.get("template", {})
            template = CommitTemplate(
                subject=template_data.get("subject", "[{op}] {path} – {summary}"),
                body=template_data.get("body"),
                trailers=template_data.get("trailers"),
                enforce_unique_window=template_data.get("enforce_unique_window", 100)
            )
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
            return [TextContent(type="text", text=result.model_dump_json())]
        
        elif name == "read_with_history":
            repo_ref = RepoRef(root=arguments["repo"])
            result = read_with_history_tool(repo_ref, arguments["path"], arguments.get("history_limit", 10))
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "start_staged":
            repo_ref = RepoRef(root=arguments["repo"])
            result = start_staged_tool(repo_ref, arguments.get("ticket"))
            return [TextContent(type="text", text=result.model_dump_json())]
        
        elif name == "staged_write":
            repo_ref = RepoRef(root=arguments["repo"])
            template = load_default_template()
            request = WriteRequest(
                repo=repo_ref,
                path=arguments["path"],
                content=arguments["content"],
                template=template,
                op="staged",
                summary=arguments["summary"]
            )
            result = staged_write_tool(arguments["session_id"], request)
            return [TextContent(type="text", text=result.model_dump_json())]
        
        elif name == "staged_preview":
            result = staged_preview_tool(arguments["session_id"])
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "finalize_staged":
            options = FinalizeOptions(
                strategy=arguments.get("strategy", "merge-ff"),
                delete_work_branch=arguments.get("delete_work_branch", True)
            )
            result = finalize_tool(arguments["session_id"], options)
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "abort_staged":
            result = abort_tool(arguments["session_id"])
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "extract":
            repo_ref = RepoRef(root=arguments["repo"])
            intent = ReadIntent(
                path=arguments["path"],
                query=arguments["query"],
                regex=arguments.get("regex", False),
                before=arguments.get("before", 3),
                after=arguments.get("after", 3),
                max_spans=arguments.get("max_spans", 20),
                include_content=arguments.get("include_content", False),
                history_limit=arguments.get("history_limit", 10)
            )
            result = extract_tool(repo_ref, intent)
            return [TextContent(type="text", text=result.model_dump_json())]
        
        elif name == "answer_about_file":
            repo_ref = RepoRef(root=arguments["repo"])
            result = answer_about_file_tool(
                repo_ref, 
                arguments["path"], 
                arguments["question"],
                arguments.get("before", 3),
                arguments.get("after", 3),
                arguments.get("max_spans", 20)
            )
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "replace_and_commit":
            repo_ref = RepoRef(root=arguments["repo"])
            template_data = arguments.get("template", {})
            template = CommitTemplate(
                subject=template_data.get("subject", "[{op}] {path} – {summary}"),
                body=template_data.get("body"),
                trailers=template_data.get("trailers"),
                enforce_unique_window=template_data.get("enforce_unique_window", 100)
            )
            result = replace_and_commit(
                repo_ref,
                arguments["path"],
                arguments["search"],
                arguments["replace"],
                arguments.get("regex", False),
                template,
                arguments.get("summary", "text replacement")
            )
            return [TextContent(type="text", text=json.dumps({"commit_sha": result}))]
        
        elif name == "batch_replace_and_commit":
            repo_ref = RepoRef(root=arguments["repo"])
            template_data = arguments.get("template", {})
            template = CommitTemplate(
                subject=template_data.get("subject", "[{op}] {path} – {summary}"),
                body=template_data.get("body"),
                trailers=template_data.get("trailers"),
                enforce_unique_window=template_data.get("enforce_unique_window", 100)
            )
            result = batch_replace_and_commit(
                repo_ref,
                arguments["replacements"],
                template,
                arguments.get("summary", "batch text replacement")
            )
            return [TextContent(type="text", text=json.dumps({"commit_shas": result}))]
        
        elif name == "preview_diff":
            repo_ref = RepoRef(root=arguments["repo"])
            result = preview_diff(
                repo_ref,
                arguments["path"],
                arguments["modified_content"],
                arguments.get("ignore_whitespace", False),
                arguments.get("context_lines", 3)
            )
            return [TextContent(type="text", text=json.dumps({"diff": result}))]
        
        elif name == "apply_patch_and_commit":
            repo_ref = RepoRef(root=arguments["repo"])
            template_data = arguments.get("template", {})
            template = CommitTemplate(
                subject=template_data.get("subject", "[{op}] {path} – {summary}"),
                body=template_data.get("body"),
                trailers=template_data.get("trailers"),
                enforce_unique_window=template_data.get("enforce_unique_window", 100)
            )
            result = apply_patch_and_commit(
                repo_ref,
                arguments["path"],
                arguments["patch"],
                template,
                arguments.get("summary", "apply patch")
            )
            return [TextContent(type="text", text=json.dumps({"commit_sha": result}))]
        
        elif name == "read_file":
            repo_ref = RepoRef(root=arguments["repo"])
            result = read_file(repo_ref, arguments["path"])
            return [TextContent(type="text", text=json.dumps({"content": result}))]
        
        elif name == "stat_file":
            repo_ref = RepoRef(root=arguments["repo"])
            result = stat_file(repo_ref, arguments["path"])
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "list_dir":
            repo_ref = RepoRef(root=arguments["repo"])
            result = list_dir(repo_ref, arguments["path"], arguments.get("recursive", False))
            return [TextContent(type="text", text=json.dumps({"files": result}))]
        
        elif name == "make_dir":
            repo_ref = RepoRef(root=arguments["repo"])
            result = make_dir(repo_ref, arguments["path"], arguments.get("recursive", False))
            return [TextContent(type="text", text=json.dumps(result))]
        
        elif name == "lint_commit_message":
            template_data = arguments["template"]
            template = CommitTemplate(
                subject=template_data["subject"],
                body=template_data.get("body"),
                trailers=template_data.get("trailers"),
                enforce_unique_window=template_data.get("enforce_unique_window", 100)
            )
            result = lint_commit_msg(template, arguments["variables"])
            return [TextContent(type="text", text=json.dumps(result))]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except Exception as e:
        logger.error(f"Error in tool call {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Run the MCP server."""
    # Run with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())