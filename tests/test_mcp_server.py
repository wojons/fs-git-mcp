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

async def test_mcp_server():
    """Test MCP server with stdio transport."""
    print("🧪 Testing MCP Server...")
    
    # Start the MCP server process
    process = await asyncio.create_subprocess_exec(
        sys.executable, "standalone_fastmcp_server.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    if not process.stdin or not process.stdout:
        print("❌ Failed to start MCP server process")
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
        process.stdin.write((json.dumps(init_request) + "\n").encode())
        await process.stdin.drain()
        
        # Read response
        response_line = await process.stdout.readline()
        if response_line:
            response = json.loads(response_line.decode().strip())
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
        process.stdin.write((json.dumps(tools_request) + "\n").encode())
        await process.stdin.drain()
        
        # Read tools response
        tools_response_line = await process.stdout.readline()
        if tools_response_line:
            tools_response = json.loads(tools_response_line.decode().strip())
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
            process.terminate()
            await process.wait()
        except:
            pass

async def main():
    """Run all tests."""
    print("🚀 Starting MCP Server Tests\n")
    
    success = await test_mcp_server()
    
    if success:
        print("\n🎉 All tests passed! MCP server is working correctly.")
        sys.exit(0)
    else:
        print("\n💥 Tests failed! Check MCP server implementation.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())