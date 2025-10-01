#!/usr/bin/env python3
"""Test script for minimal FastMCP server."""

import asyncio
import json
import sys

async def test_minimal_server():
    """Test minimal FastMCP server."""
    print("🧪 Testing Minimal FastMCP Server...")
    
    # Start the MCP server process
    process = await asyncio.create_subprocess_exec(
        sys.executable, "test_minimal_fastmcp.py",
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
            
            for tool in tools:
                print(f"  - {tool.get('name')}: {tool.get('description', 'No description')}")
        
        print("\n✅ Minimal FastMCP server test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Minimal FastMCP server test failed: {e}")
        return False
    
    finally:
        # Clean shutdown
        try:
            process.terminate()
            await process.wait()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_minimal_server())