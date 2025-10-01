#!/usr/bin/env python3
"""
Test script to verify MCP server functionality end-to-end.
"""

import subprocess
import json
import sys
import os
import tempfile
import time

def send_mcp_request(proc, request):
    """Send a JSON-RPC request to the MCP server and get response."""
    request_json = json.dumps(request) + "\n"
    proc.stdin.write(request_json.encode('utf-8'))
    proc.stdin.flush()
    
    # Read response
    line = proc.stdout.readline()
    if not line:
        return None
    
    try:
        return json.loads(line.decode('utf-8').strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

def test_mcp_server():
    """Test the MCP server with basic operations."""
    print("🧪 Testing MCP Server Functionality")
    
    # Start the MCP server process
    proc = subprocess.Popen(
        [sys.executable, "mcp_server/server_fastmcp_new.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    try:
        # Initialize the MCP connection
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {"listChanged": True}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        response = send_mcp_request(proc, init_request)
        if not response or "result" not in response:
            print("❌ Failed to initialize MCP connection")
            return False
        
        print("✅ MCP server initialized successfully")
        
        # Send initialized notification
        init_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        send_mcp_request(proc, init_notification)
        
        # List available tools
        tools_request = {
            "jsonrpc": "2.0", 
            "id": 2,
            "method": "tools/list"
        }
        
        response = send_mcp_request(proc, tools_request)
        if not response or "result" not in response:
            print("❌ Failed to list tools")
            return False
        
        tools = response["result"].get("tools", [])
        tool_names = [tool.get("name") for tool in tools]
        
        print(f"✅ Found {len(tools)} tools: {', '.join(tool_names)}")
        
        # Check for expected tools
        expected_tools = [
            "write_and_commit",
            "read_with_history", 
            "start_staged",
            "extract"
        ]
        
        missing_tools = [tool for tool in expected_tools if tool not in tool_names]
        if missing_tools:
            print(f"⚠️  Missing expected tools: {', '.join(missing_tools)}")
        else:
            print("✅ All expected tools are available")
        
        # Test a simple operation - create a temp repo and write a file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True)
            
            # Test write_and_commit tool
            test_file = os.path.join(temp_dir, "test.txt")
            write_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "write_and_commit",
                    "arguments": {
                        "repo": {"root": temp_dir},
                        "path": "test.txt",
                        "content": "Hello from MCP server!",
                        "op": "add",
                        "summary": "test file creation"
                    }
                }
            }
            
            response = send_mcp_request(proc, write_request)
            if not response or "result" not in response:
                print("❌ Failed to write and commit file")
                return False
            
            print("✅ Successfully wrote and committed file via MCP")
            
            # Verify the file was created and committed
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
            
            # Check git log
            result = subprocess.run(["git", "log", "--oneline"], cwd=temp_dir, capture_output=True, text=True)
            if "test file creation" in result.stdout:
                print("✅ Git commit verified")
            else:
                print("❌ Git commit not found")
                return False
        
        print("🎉 All MCP server tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
    
    finally:
        # Clean up the server process
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()

if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)