#!/usr/bin/env python3
"""
Test the format of tool responses from the MCP server.
"""

import subprocess
import json
import sys
import os
import time
import tempfile

def test_tool_response_format():
    """Test the response format of MCP tools."""
    print("🔍 Testing Tool Response Format")
    
    # Start server
    proc = subprocess.Popen(
        [sys.executable, "mcp_server/server_fastmcp_new.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    if proc.stdin is None or proc.stdout is None:
        print("❌ Failed to start server")
        return False
    
    try:
        time.sleep(1)
        
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
        if not line:
            print("❌ No init response")
            return False
        
        init_response = json.loads(line.decode('utf-8').strip())
        if "result" not in init_response:
            print(f"❌ Init failed: {init_response}")
            return False
        
        print("✅ Server initialized")
        
        # Send initialized notification
        init_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        notification_json = json.dumps(init_notification) + "\n"
        proc.stdin.write(notification_json.encode('utf-8'))
        proc.stdin.flush()
        
        # Create temp directory for a real test
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True)
            
            # Test a simple tool call
            write_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "write_and_commit",
                    "arguments": {
                        "repo": {"root": temp_dir},
                        "path": "test.txt",
                        "content": "Hello world!",
                        "op": "add",
                        "summary": "test commit"
                    }
                }
            }
            
            write_json = json.dumps(write_request) + "\n"
            proc.stdin.write(write_json.encode('utf-8'))
            proc.stdin.flush()
            
            # Read response
            time.sleep(1)
            response_line = proc.stdout.readline()
            if not response_line:
                print("❌ No tool response")
                return False
            
            tool_response = json.loads(response_line.decode('utf-8').strip())
            print(f"Debug: tool response = {json.dumps(tool_response, indent=2)}")
            
            if "result" in tool_response:
                result = tool_response["result"]
                print(f"✅ Tool call succeeded")
                print(f"   Result type: {type(result)}")
                print(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
                
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    print(f"   Content type: {type(content)}")
                    print(f"   Content value: {content}")
                    
                    # Check if the file was actually created
                    test_file = os.path.join(temp_dir, "test.txt")
                    if os.path.exists(test_file):
                        with open(test_file, 'r') as f:
                            actual_content = f.read()
                            print(f"   Actual file content: {repr(actual_content)}")
                    else:
                        print("   ❌ File was not created")
                
                return True
            elif "error" in tool_response:
                print(f"❌ Tool call failed: {tool_response['error']}")
                return False
            else:
                print(f"❓ Unexpected response: {tool_response}")
                return False
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()

if __name__ == "__main__":
    test_tool_response_format()