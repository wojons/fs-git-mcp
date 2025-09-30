#!/usr/bin/env python3
"""
Comprehensive tests for the MCP server protocol.
"""

import json
import tempfile
import subprocess
import os
import pytest
from pathlib import Path
from mcp_server.server_simple import MCPServer


class TestMCPServer:
    """Test MCP server functionality."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize git repo
            subprocess.run(["git", "init", temp_dir], check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
            
            # Create initial file
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("Hello, World!\n")
            subprocess.run(["git", "-C", temp_dir, "add", "test.txt"], check=True)
            subprocess.run(["git", "-C", temp_dir, "commit", "-m", "Initial commit"], check=True)
            
            yield temp_dir
    
    def test_list_tools(self):
        """Test listing available tools."""
        server = MCPServer()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "list_tools",
            "params": {}
        }
        
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "tools" in response["result"]
        
        tools = response["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]
        
        # Check that all expected tools are present
        expected_tools = [
            "write_and_commit",
            "read_with_history", 
            "start_staged",
            "staged_write",
            "staged_preview",
            "finalize_staged",
            "abort_staged",
            "extract",
            "answer_about_file",
            "replace_and_commit",
            "batch_replace_and_commit",
            "preview_diff",
            "apply_patch_and_commit",
            "read_file",
            "stat_file",
            "list_dir",
            "make_dir",
            "lint_commit_message",
        ]
        
        for tool in expected_tools:
            assert tool in tool_names, f"Tool {tool} not found in response"
    
    def test_write_and_commit(self, temp_repo):
        """Test write_and_commit tool."""
        server = MCPServer()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "write_and_commit",
                "arguments": {
                    "repo": temp_repo,
                    "path": "new_file.txt",
                    "content": "New content\n",
                    "template": {
                        "subject": "[{op}] {path} – {summary}"
                    },
                    "op": "add",
                    "summary": "test file creation"
                }
            }
        }
        
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        
        result = json.loads(response["result"]["content"][0]["text"])
        assert "commit_sha" in result
        assert "path" in result
        assert result["path"] == "new_file.txt"
        
        # Verify file was created and committed
        file_path = Path(temp_repo) / "new_file.txt"
        assert file_path.exists()
        assert file_path.read_text() == "New content\n"
    
    def test_read_with_history(self, temp_repo):
        """Test read_with_history tool."""
        server = MCPServer()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "read_with_history",
                "arguments": {
                    "repo": temp_repo,
                    "path": "test.txt",
                    "history_limit": 5
                }
            }
        }
        
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        
        result = json.loads(response["result"]["content"][0]["text"])
        assert "path" in result
        assert "history" in result
        assert "content" in result
        
        assert result["path"] == "test.txt"
        assert len(result["history"]) >= 1
        assert result["content"] == "Hello, World!\n"
    
    def test_extract(self, temp_repo):
        """Test extract tool."""
        server = MCPServer()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "extract",
                "arguments": {
                    "repo": temp_repo,
                    "path": "test.txt",
                    "query": "Hello",
                    "before": 1,
                    "after": 1
                }
            }
        }
        
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        
        result = json.loads(response["result"]["content"][0]["text"])
        assert "path" in result
        assert "spans" in result
        assert "history" in result
        
        assert result["path"] == "test.txt"
        assert len(result["spans"]) > 0
        assert len(result["history"]) >= 1
    
    def test_staged_workflow(self, temp_repo):
        """Test complete staged workflow."""
        server = MCPServer()
        
        # Start staged session
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "start_staged",
                "arguments": {
                    "repo": temp_repo,
                    "ticket": "T-123"
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        session_id = result["id"]
        
        # Staged write
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "call_tool",
            "params": {
                "name": "staged_write",
                "arguments": {
                    "session_id": session_id,
                    "repo": temp_repo,
                    "path": "staged_file.txt",
                    "content": "Staged content\n",
                    "summary": "staged file creation"
                }
            }
        }
        
        response = server.handle_request(request)
        assert "result" in response
        
        # Preview staged changes
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "call_tool",
            "params": {
                "name": "staged_preview",
                "arguments": {
                    "session_id": session_id
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        assert "diff" in result
        assert "staged_file.txt" in result["diff"]
        
        # Finalize staged session
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "call_tool",
            "params": {
                "name": "finalize_staged",
                "arguments": {
                    "session_id": session_id,
                    "strategy": "merge-ff"
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        assert "merged_sha" in result
        
        # Verify file was committed to main branch
        file_path = Path(temp_repo) / "staged_file.txt"
        assert file_path.exists()
        assert file_path.read_text() == "Staged content\n"
    
    def test_replace_and_commit(self, temp_repo):
        """Test replace_and_commit tool."""
        server = MCPServer()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "replace_and_commit",
                "arguments": {
                    "repo": temp_repo,
                    "path": "test.txt",
                    "search": "World",
                    "replace": "MCP",
                    "template": {
                        "subject": "[{op}] {path} – {summary}"
                    },
                    "summary": "text replacement"
                }
            }
        }
        
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        
        result = json.loads(response["result"]["content"][0]["text"])
        assert "commit_sha" in result
        
        # Verify replacement was made
        file_path = Path(temp_repo) / "test.txt"
        assert file_path.read_text() == "Hello, MCP!\n"
    
    def test_apply_patch_and_commit(self, temp_repo):
        """Test apply_patch_and_commit tool."""
        server = MCPServer()
        
        patch_content = """--- a/test.txt
+++ b/test.txt
@@ -1 +1 @@
-Hello, World!
+Hello, Patched!
"""
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "apply_patch_and_commit",
                "arguments": {
                    "repo": temp_repo,
                    "path": "test.txt",
                    "patch": patch_content,
                    "template": {
                        "subject": "[{op}] {path} – {summary}"
                    },
                    "summary": "apply patch"
                }
            }
        }
        
        response = server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        
        result = json.loads(response["result"]["content"][0]["text"])
        assert "commit_sha" in result
        
        # Verify patch was applied
        file_path = Path(temp_repo) / "test.txt"
        assert file_path.read_text() == "Hello, Patched!\n"
    
    def test_file_system_operations(self, temp_repo):
        """Test file system operations."""
        server = MCPServer()
        
        # Test read_file
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "read_file",
                "arguments": {
                    "repo": temp_repo,
                    "path": "test.txt"
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        assert result["content"] == "Hello, World!\n"
        
        # Test list_dir
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "call_tool",
            "params": {
                "name": "list_dir",
                "arguments": {
                    "repo": temp_repo,
                    "path": "."
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        assert "test.txt" in result["files"]
        
        # Test make_dir
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "call_tool",
            "params": {
                "name": "make_dir",
                "arguments": {
                    "repo": temp_repo,
                    "path": "new_dir"
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        assert result["ok"]
        
        # Verify directory was created
        dir_path = Path(temp_repo) / "new_dir"
        assert dir_path.exists()
        assert dir_path.is_dir()
    
    def test_lint_commit_message(self):
        """Test lint_commit_message tool."""
        server = MCPServer()
        
        # Test valid template
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "lint_commit_message",
                "arguments": {
                    "template": {
                        "subject": "[{op}] {path} – {summary}"
                    },
                    "variables": {
                        "op": "edit",
                        "path": "test.txt",
                        "summary": "test edit"
                    }
                }
            }
        }
        
        response = server.handle_request(request)
        print(f"Response: {response}")
        if "result" in response:
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["ok"] is True
        else:
            print(f"Error: {response['error']}")
        
        # Test invalid template (too long)
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "call_tool",
            "params": {
                "name": "lint_commit_message",
                "arguments": {
                    "template": {
                        "subject": "This is a very long commit message subject that exceeds the 72 character limit"
                    },
                    "variables": {
                        "op": "edit",
                        "path": "test.txt",
                        "summary": "test edit"
                    }
                }
            }
        }
        
        response = server.handle_request(request)
        result = json.loads(response["result"]["content"][0]["text"])
        assert result["ok"] is False
        assert len(result["errors"]) > 0
    
    def test_error_handling(self, temp_repo):
        """Test error handling for invalid requests."""
        server = MCPServer()
        
        # Test unknown method
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown_method",
            "params": {}
        }
        
        response = server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32601
        
        # Test unknown tool
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "call_tool",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            }
        }
        
        response = server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32601
        
        # Test invalid parameters (missing required field)
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "call_tool",
            "params": {
                "name": "write_and_commit",
                "arguments": {
                    "repo": temp_repo
                    # Missing required 'path' and 'content'
                }
            }
        }
        
        response = server.handle_request(request)
        assert "error" in response
        assert response["error"]["code"] == -32603


if __name__ == "__main__":
    pytest.main([__file__, "-v"])