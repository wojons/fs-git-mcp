#!/usr/bin/env python3
"""
Basic MCP server test focusing on core functionality.
"""

import subprocess
import json
import sys
import os
import time
import tempfile

class SimpleMCPClient:
    def __init__(self, server_path):
        self.proc = subprocess.Popen(
            [sys.executable, server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        self.request_id = 1
        
        if self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("Failed to open stdin/stdout for server process")
    
    def send_request(self, method, params=None, is_notification=False):
        """Send a JSON-RPC request to the MCP server."""
        if self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("Server process stdin/stdout is not available")
        
        request = {
            "jsonrpc": "2.0",
            "method": method
        }
        
        if not is_notification:
            request["id"] = self.request_id
            self.request_id += 1
        
        if params is not None:
            request["params"] = params
        
        request_json = json.dumps(request) + "\n"
        self.proc.stdin.write(request_json.encode('utf-8'))
        self.proc.stdin.flush()
        
        if is_notification:
            return None
        
        # Read response with timeout
        time.sleep(0.5)  # Give server time to process
        
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("No response from server")
        
        response = json.loads(line.decode('utf-8').strip())
        
        if "error" in response:
            raise RuntimeError(f"MCP Error: {response['error'].get('message', 'Unknown error')}")
        
        return response.get("result")
    
    def initialize(self):
        """Initialize the MCP connection."""
        result = self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {"listChanged": True}},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        })
        
        # Send initialized notification
        self.send_request("notifications/initialized", is_notification=True)
        
        return result
    
    def call_tool(self, name, arguments):
        """Call a specific tool."""
        response = self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        
        # Extract actual result from FastMCP response format
        if response and "structuredContent" in response and "result" in response["structuredContent"]:
            return response["structuredContent"]["result"]
        elif response and "content" in response:
            # Fallback to content if structuredContent not available
            return response["content"]
        else:
            return response
    
    def close(self):
        """Close the connection."""
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except:
            self.proc.kill()

def test_basic_mcp_functionality():
    """Test basic MCP server functionality."""
    print("🧪 Basic MCP Server Functionality Test")
    
    client = SimpleMCPClient("mcp_server/server_fastmcp_new.py")
    
    try:
        # Initialize
        server_info = client.initialize()
        if not server_info or 'serverInfo' not in server_info:
            print("❌ Failed to initialize server")
            return False
            
        print(f"✅ Connected to {server_info['serverInfo']['name']} v{server_info['serverInfo']['version']}")
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"📁 Using temporary directory: {temp_dir}")
            
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True)
            
            # Test 1: write_and_commit
            print("\n📝 Test 1: write_and_commit")
            result = client.call_tool("write_and_commit", {
                "repo": {"root": temp_dir},
                "path": "test.txt",
                "content": "Hello from MCP server!",
                "op": "add",
                "summary": "create test file"
            })
            if not result:
                print("❌ write_and_commit returned None")
                return False
            print(f"✅ File written and committed: {result}")
            
            # Verify file exists
            test_file = os.path.join(temp_dir, "test.txt")
            if os.path.exists(test_file):
                with open(test_file, 'r') as f:
                    content = f.read()
                    if "Hello from MCP server!" in content:
                        print("✅ File content verified")
                    else:
                        print("❌ File content incorrect")
                        return False
            else:
                print("❌ File was not created")
                return False
            
            # Test 2: read_with_history
            print("\n📖 Test 2: read_with_history")
            result = client.call_tool("read_with_history", {
                "repo": {"root": temp_dir},
                "path": "test.txt",
                "history_limit": 5
            })
            if not result or 'history' not in result:
                print("❌ read_with_history failed")
                return False
            print(f"✅ Read file with {len(result['history'])} history entries")
            
            # Test 3: extract (reader subagent)
            print("\n🔍 Test 3: extract (reader subagent)")
            result = client.call_tool("extract", {
                "repo": {"root": temp_dir},
                "path": "test.txt",
                "query": "Hello",
                "before": 2,
                "after": 2
            })
            if not result or 'spans' not in result:
                print("❌ extract failed")
                return False
            print(f"✅ Extract found {len(result['spans'])} matching spans")
            
            # Test 4: replace_and_commit
            print("\n🔄 Test 4: replace_and_commit")
            result = client.call_tool("replace_and_commit", {
                "repo": {"root": temp_dir},
                "path": "test.txt",
                "search": "MCP server",
                "replace": "MCP replace tool",
                "op": "edit",
                "summary": "text replacement test"
            })
            if not result:
                print("❌ replace_and_commit failed")
                return False
            print(f"✅ Text replaced and committed: {result}")
            
            # Verify replacement
            with open(test_file, 'r') as f:
                content = f.read()
                if "Hello from MCP replace tool!" in content:
                    print("✅ Text replacement verified")
                else:
                    print("❌ Text replacement failed")
                    return False
            
            # Test 5: read_file (fs_io integration)
            print("\n📁 Test 5: read_file (fs_io integration)")
            result = client.call_tool("read_file", {
                "repo": {"root": temp_dir},
                "path": "test.txt"
            })
            if not result or 'content' not in result:
                print("❌ read_file failed")
                return False
            print(f"✅ Read file via fs_io: {len(result['content'])} characters")
            
            # Test 6: preview_diff
            print("\n🔬 Test 6: preview_diff")
            result = client.call_tool("preview_diff", {
                "repo": {"root": temp_dir},
                "path": "test.txt",
                "modified_content": "Hello from diff preview!\nThis is a test.\n"
            })
            if not result or 'diff' not in result:
                print("❌ preview_diff failed")
                return False
            print(f"✅ Diff preview generated: {len(result['diff'])} characters")
            
        print("\n🎉 All basic MCP server tests passed!")
        print("✅ Core functionality verified:")
        print("   - File operations with git commits")
        print("   - Reader subagent for content extraction")
        print("   - Text replacement and diff tools")
        print("   - Integration with file system operations")
        print("   - Git history tracking")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        client.close()

if __name__ == "__main__":
    success = test_basic_mcp_functionality()
    sys.exit(0 if success else 1)