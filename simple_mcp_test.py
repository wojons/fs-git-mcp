#!/usr/bin/env python3
"""
Simple test to verify MCP server can start and handle basic requests.
"""

import subprocess
import json
import sys
import os
import time

def test_mcp_server_basic():
    """Basic test of MCP server startup and initialization."""
    print("🧪 Testing MCP Server Basic Functionality")
    
    # Start the MCP server process
    proc = subprocess.Popen(
        [sys.executable, "mcp_server/server_fastmcp_new.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    if proc.stdin is None or proc.stdout is None:
        print("❌ Failed to open stdin/stdout for server process")
        return False
    
    try:
        # Give the server a moment to start
        time.sleep(1)
        
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
        
        # Send request
        request_json = json.dumps(init_request) + "\n"
        proc.stdin.write(request_json.encode('utf-8'))
        proc.stdin.flush()
        
        # Read response with timeout
        try:
            # Use select to check if there's data available
            import select
            ready, _, _ = select.select([proc.stdout], [], [], 5)  # 5 second timeout
            
            if ready:
                line = proc.stdout.readline()
                if line:
                    response = json.loads(line.decode('utf-8').strip())
                    if "result" in response:
                        print("✅ MCP server initialized successfully")
                        print(f"   Server info: {response['result'].get('serverInfo', {})}")
                        
                        # Test tools/list
                        tools_request = {
                            "jsonrpc": "2.0", 
                            "id": 2,
                            "method": "tools/list",
                            "params": {}
                        }
                        
                        tools_json = json.dumps(tools_request) + "\n"
                        proc.stdin.write(tools_json.encode('utf-8'))
                        proc.stdin.flush()
                        
                        ready, _, _ = select.select([proc.stdout], [], [], 5)
                        if ready:
                            tools_line = proc.stdout.readline()
                            if tools_line:
                                tools_response = json.loads(tools_line.decode('utf-8').strip())
                                print(f"Debug: tools response = {tools_response}")
                                if "result" in tools_response and "tools" in tools_response["result"]:
                                    tools = tools_response["result"]["tools"]
                                    print(f"✅ Found {len(tools)} tools")
                                    for tool in tools[:3]:  # Show first 3 tools
                                        print(f"   - {tool.get('name', 'unnamed')}")
                                    if len(tools) > 3:
                                        print(f"   ... and {len(tools) - 3} more")
                                    return True
                                else:
                                    print("❌ Invalid tools/list response")
                                    print(f"   Expected 'result.tools', got: {list(tools_response.keys()) if isinstance(tools_response, dict) else 'not a dict'}")
                                    return False
                            else:
                                print("❌ No response to tools/list")
                                return False
                        else:
                            print("❌ Timeout waiting for tools/list response")
                            return False
                    else:
                        print(f"❌ Initialize response error: {response}")
                        return False
                else:
                    print("❌ No response to initialize")
                    return False
            else:
                print("❌ Timeout waiting for initialize response")
                return False
                
        except ImportError:
            # Fallback without select
            print("⚠️  select module not available, using simpler test")
            line = proc.stdout.readline()
            if line:
                response = json.loads(line.decode('utf-8').strip())
                if "result" in response:
                    print("✅ MCP server responded to initialize")
                    return True
                else:
                    print(f"❌ Initialize response error: {response}")
                    return False
            else:
                print("❌ No response to initialize")
                return False
        
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
    
    return True

if __name__ == "__main__":
    success = test_mcp_server_basic()
    if success:
        print("🎉 MCP server basic test passed!")
    sys.exit(0 if success else 1)