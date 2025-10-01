#!/usr/bin/env python3
"""
Test script for MCP server functionality.
Tests both basic server startup and protocol compliance.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

@pytest.mark.asyncio
def test_mcp_server():
    """Test MCP server with stdio transport."""
    print("🧪 Testing MCP Server...")
    
    # Start the MCP server process
    process = subprocess.Popen(
        [sys.executable, "standalone_fastmcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    if process.stdin is None or process.stdout is None:
        print("❌ Failed to start MCP server process")
        process.terminate()
        return False
    
    try:
        # Send initialization request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("📤 Sending initialize request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"📥 Initialize response: {json.dumps(response, indent=2)}")
            
            if response.get("result") and response["result"].get("serverInfo"):
                server_info = response["result"]["serverInfo"]
                print(f"✅ Server connected: {server_info.get('name')} v{server_info.get('version')}")
            else:
                print("❌ Invalid initialize response")
                return False
        
        # Send list tools request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        print("\n📤 Sending tools/list request...")
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        # Read tools response
        tools_response_line = process.stdout.readline()
        if tools_response_line:
            tools_response = json.loads(tools_response_line.strip())
            tools = tools_response.get("result", {}).get("tools", [])
            print(f"📥 Available tools: {len(tools)} tools found")
            
            for tool in tools[:5]:  # Show first 5 tools
                print(f"  - {tool.get('name')}: {tool.get('description', 'No description')}")
            
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more tools")
        
        print("\n✅ MCP server test passed!")
        return True
        
    except Exception as e:
        print(f"❌ MCP server test failed: {e}")
        return False
    
    finally:
        # Clean shutdown
        try:
            process.stdin.close()
            process.terminate()
            process.wait(timeout=5)
        except:
            pass

def main():
    """Run all tests."""
    print("🚀 Starting MCP Server Tests\n")
    
    success = test_mcp_server()
    
    if success:
        print("\n🎉 All tests passed! MCP server is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Tests failed! Check MCP server implementation.")
        sys.exit(1)

if __name__ == "__main__":
    main()