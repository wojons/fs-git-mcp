#!/usr/bin/env python3
"""
Debug script to check what methods the MCP server actually supports.
"""

import subprocess
import json
import sys
import os
import time

def test_mcp_methods():
    """Test different method calls to see what the server supports."""
    print("🔍 Debugging MCP Server Methods")
    
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
        time.sleep(1)  # Give server time to start
        
        # Initialize
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
        
        request_json = json.dumps(init_request) + "\n"
        proc.stdin.write(request_json.encode('utf-8'))
        proc.stdin.flush()
        
        # Read init response
        line = proc.stdout.readline()
        if line:
            response = json.loads(line.decode('utf-8').strip())
            if "result" in response:
                print("✅ Server initialized")
            else:
                print(f"❌ Init failed: {response}")
                return False
        
        # Send initialized notification
        init_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        notification_json = json.dumps(init_notification) + "\n"
        proc.stdin.write(notification_json.encode('utf-8'))
        proc.stdin.flush()
        
        # Try different method calls
        methods_to_test = [
            ("tools/list", {}),
            ("tools/list", None),
            ("tools/call", {"name": "write_and_commit", "arguments": {}}),
            ("ping", {}),
            ("list_tools", {}),
        ]
        
        for i, (method, params) in enumerate(methods_to_test):
            request_id = i + 2
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method
            }
            
            if params is not None:
                request["params"] = params
            
            print(f"\n🧪 Testing method: {method}")
            request_json = json.dumps(request) + "\n"
            proc.stdin.write(request_json.encode('utf-8'))
            proc.stdin.flush()
            
            # Read response with short timeout
            time.sleep(0.5)
            
            # Try to read response
            try:
                line = proc.stdout.readline()
                if line:
                    response = json.loads(line.decode('utf-8').strip())
                    if "result" in response:
                        print(f"✅ {method} succeeded")
                        if isinstance(response["result"], dict) and "tools" in response["result"]:
                            tools = response["result"]["tools"]
                            print(f"   Found {len(tools)} tools:")
                            for tool in tools:
                                print(f"     - {tool.get('name', 'unnamed')}")
                    elif "error" in response:
                        print(f"❌ {method} failed: {response['error'].get('message', 'unknown error')}")
                    else:
                        print(f"❓ {method} unexpected response: {response}")
                else:
                    print(f"❌ {method} no response")
            except Exception as e:
                print(f"❌ {method} error reading response: {e}")
        
        print("\n🎯 Method testing completed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()

if __name__ == "__main__":
    test_mcp_methods()