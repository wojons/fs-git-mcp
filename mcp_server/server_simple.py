#!/usr/bin/env python3
"""
Simple MCP Server for Git-enforced filesystem operations.
 
This is a basic JSON-RPC server that can be extended to support the full MCP protocol.
For now, it provides the core functionality in a simple format.
"""

import json
import sys
from typing import Any, Dict, List, Optional

# Import our tools
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

class MCPServer:
    """Simple MCP server implementation."""
    
    def get_repo_ref(self, params: Dict[str, Any]) -> RepoRef:
        repo_param = params.get("repo")
        if isinstance(repo_param, dict):
            root = repo_param.get("root")
            if root is None:
                raise ValueError("Repo dict missing root key")
            branch = repo_param.get("branch")
        else:
            root = repo_param
            if not isinstance(root, str):
                raise ValueError("Repo parameter must be a string path or a dict with root key")
            branch = None
        return RepoRef(root=root, branch=branch)
    
    def __init__(self):
        self.tools = {
            "write_and_commit": self.handle_write_and_commit,
            "read_with_history": self.handle_read_with_history,
            "start_staged": self.handle_start_staged,
            "staged_write": self.handle_staged_write,
            "staged_preview": self.handle_staged_preview,
            "finalize_staged": self.handle_finalize_staged,
            "abort_staged": self.handle_abort_staged,
            "extract": self.handle_extract,
            "answer_about_file": self.handle_answer_about_file,
            "replace_and_commit": self.handle_replace_and_commit,
            "batch_replace_and_commit": self.handle_batch_replace_and_commit,
            "preview_diff": self.handle_preview_diff,
            "apply_patch_and_commit": self.handle_apply_patch_and_commit,
            "read_file": self.handle_read_file,
            "stat_file": self.handle_stat_file,
            "list_dir": self.handle_list_dir,
            "make_dir": self.handle_make_dir,
            "lint_commit_message": self.handle_lint_commit_message,
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a JSON-RPC request."""
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            if method == "list_tools":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": [
                            {
                                "name": "write_and_commit",
                                "description": "Write a file and create an atomic git commit with templated message"
                            },
                            {
                                "name": "read_with_history", 
                                "description": "Read file content with git history"
                            },
                            {
                                "name": "start_staged",
                                "description": "Start a staged editing session"
                            },
                            {
                                "name": "staged_write",
                                "description": "Write to a staged session"
                            },
                            {
                                "name": "staged_preview",
                                "description": "Preview staged changes"
                            },
                            {
                                "name": "finalize_staged",
                                "description": "Finalize a staged session"
                            },
                            {
                                "name": "abort_staged",
                                "description": "Abort a staged session"
                            },
                            {
                                "name": "extract",
                                "description": "Extract relevant spans from a file based on query"
                            },
                            {
                                "name": "answer_about_file",
                                "description": "Answer questions about a file's content"
                            },
                            {
                                "name": "replace_and_commit",
                                "description": "Replace text in file and commit"
                            },
                            {
                                "name": "batch_replace_and_commit",
                                "description": "Replace multiple patterns and commit"
                            },
                            {
                                "name": "preview_diff",
                                "description": "Preview diff between original and modified content"
                            },
                            {
                                "name": "apply_patch_and_commit",
                                "description": "Apply patch and commit"
                            },
                            {
                                "name": "read_file",
                                "description": "Read file from repository"
                            },
                            {
                                "name": "stat_file",
                                "description": "Get file statistics"
                            },
                            {
                                "name": "list_dir",
                                "description": "List directory contents"
                            },
                            {
                                "name": "make_dir",
                                "description": "Create directory"
                            },
                            {
                                "name": "lint_commit_message",
                                "description": "Validate commit message template"
                            },
                        ]
                    }
                }
            
            elif method == "call_tool":
                tool_name = params.get("name")
                tool_params = params.get("arguments", {})
                
                if tool_name in self.tools:
                    result = self.tools[tool_name](tool_params)
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2)
                                }
                            ]
                        }
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}"
                    }
                }
        
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    def handle_write_and_commit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        template_data = params.get("template", {})
        template = CommitTemplate(
            subject=template_data.get("subject", "[{op}] {path} – {summary}"),
            body=template_data.get("body"),
            trailers=template_data.get("trailers"),
            enforce_unique_window=template_data.get("enforce_unique_window", 100)
        )
        request = WriteRequest(
            repo=repo_ref,
            path=params["path"],
            content=params["content"],
            template=template,
            op=params.get("op", "write"),
            summary=params.get("summary", "file write"),
            reason=params.get("reason"),
            ticket=params.get("ticket"),
            allow_create=params.get("allow_create", True),
            allow_overwrite=params.get("allow_overwrite", True)
        )
        result = write_and_commit_tool(request)
        return result.model_dump()
    
    def handle_read_with_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        return read_with_history_tool(repo_ref, params["path"], params.get("history_limit", 10))
    
    def handle_start_staged(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = start_staged_tool(repo_ref, params.get("ticket"))
        return result.model_dump()
    
    def handle_staged_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        template = load_default_template()
        request = WriteRequest(
            repo=repo_ref,
            path=params["path"],
            content=params["content"],
            template=template,
            op="staged",
            summary=params["summary"]
        )
        result = staged_write_tool(params["session_id"], request)
        return result.model_dump()
    
    def handle_staged_preview(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = staged_preview_tool(params["session_id"])
        return result.model_dump()
    
    def handle_finalize_staged(self, params: Dict[str, Any]) -> Dict[str, Any]:
        options = FinalizeOptions(
            strategy=params.get("strategy", "merge-ff"),
            delete_work_branch=params.get("delete_work_branch", True)
        )
        result = finalize_tool(params["session_id"], options)
        return result
    
    def handle_abort_staged(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = abort_tool(params["session_id"])
        return result
    
    def handle_extract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        intent = ReadIntent(
            path=params["path"],
            query=params.get("query"),
            regex=params.get("regex", False),
            before=params.get("before", 3),
            after=params.get("after", 3),
            max_spans=params.get("max_spans", 20),
            include_content=params.get("include_content", False),
            history_limit=params.get("history_limit", 10)
        )
        result = extract_tool(repo_ref, intent)
        return result.model_dump()
    
    def handle_answer_about_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = answer_about_file_tool(
            repo_ref, 
            params["path"], 
            params["question"],
            params.get("before", 3),
            params.get("after", 3),
            params.get("max_spans", 20)
        )
        return result
    
    def handle_replace_and_commit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        template_data = params.get("template", {})
        template = CommitTemplate(
            subject=template_data.get("subject", "[{op}] {path} – {summary}"),
            body=template_data.get("body"),
            trailers=template_data.get("trailers"),
            enforce_unique_window=template_data.get("enforce_unique_window", 100)
        )
        result = replace_and_commit(
            repo_ref,
            params["path"],
            params["search"],
            params["replace"],
            params.get("regex", False),
            template,
            params.get("summary", "text replacement")
        )
        return {"commit_sha": result}
    
    def handle_batch_replace_and_commit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        template_data = params.get("template", {})
        template = CommitTemplate(
            subject=template_data.get("subject", "[{op}] {path} – {summary}"),
            body=template_data.get("body"),
            trailers=template_data.get("trailers"),
            enforce_unique_window=template_data.get("enforce_unique_window", 100)
        )
        result = batch_replace_and_commit(
            repo_ref,
            params["replacements"],
            template,
            params.get("summary", "batch text replacement")
        )
        return {"commit_shas": result}
    
    def handle_preview_diff(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = preview_diff(
            repo_ref,
            params["path"],
            params["modified_content"],
            params.get("ignore_whitespace", False),
            params.get("context_lines", 3)
        )
        return {"diff": result}
    
    def handle_apply_patch_and_commit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        template_data = params.get("template", {})
        template = CommitTemplate(
            subject=template_data.get("subject", "[{op}] {path} – {summary}"),
            body=template_data.get("body"),
            trailers=template_data.get("trailers"),
            enforce_unique_window=template_data.get("enforce_unique_window", 100)
        )
        result = apply_patch_and_commit(
            repo_ref,
            params["path"],
            params["patch"],
            template,
            params.get("summary", "apply patch")
        )
        return {"commit_sha": result}
    
    def handle_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = read_file(repo_ref, params["path"])
        return {"content": result}
    
    def handle_stat_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = stat_file(repo_ref, params["path"])
        return result
    
    def handle_list_dir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = list_dir(repo_ref, params["path"], params.get("recursive", False))
        return {"files": result}
    
    def handle_make_dir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        repo_ref = self.get_repo_ref(params)
        result = make_dir(repo_ref, params["path"], params.get("recursive", False))
        return result
    
    def handle_lint_commit_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        template_data = params["template"]
        template = CommitTemplate(
            subject=template_data["subject"],
            body=template_data.get("body"),
            trailers=template_data.get("trailers"),
            enforce_unique_window=template_data.get("enforce_unique_window", 100)
        )
        result = lint_commit_msg(template, params["variables"])
        return result

def main():
    """Run the MCP server."""
    server = MCPServer()
    
    # Simple stdin/stdout server loop
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = server.handle_request(request)
            print(json.dumps(response))
            sys.stdout.flush()
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            print(json.dumps(error_response))
            sys.stdout.flush()
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    main()