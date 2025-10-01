# MCP Server Testing Guide

This guide provides comprehensive instructions for testing the fs-git MCP server using various tools and approaches.

## Table of Contents

- [Quick Testing](#quick-testing)
- [MCP Inspector Testing](#mcp-inspector-testing)
- [Python SDK Testing](#python-sdk-testing)
- [End-to-End Protocol Testing](#end-to-end-protocol-testing)
- [Troubleshooting](#troubleshooting)
- [Test Coverage](#test-coverage)

## Quick Testing

### Prerequisites

```bash
# Install dependencies
uv venv && uv pip install -e .[dev]

# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector
```

### Basic Server Test

```bash
# Test server startup
fs-git-mcp serve --transport stdio

# Or with uvx (no installation required)
uvx fs-git-mcp serve --transport stdio
```

## MCP Inspector Testing

MCP Inspector provides a visual interface for testing MCP servers.

### Installation

```bash
# Install MCP Inspector globally
npm install -g @modelcontextprotocol/inspector

# Or use npx without installation
npx @modelcontextprotocol/inspector
```

### Testing with MCP Inspector

```bash
# Start Inspector with the fs-git server
npx @modelcontextprotocol/inspector fs-git-mcp

# Or with specific transport
npx @modelcontextprotocol/inspector fs-git-mcp serve --transport stdio
```

### MCP Inspector Features

- **Tool Discovery**: View all available MCP tools (12 tools)
- **Interactive Testing**: Test each tool with custom parameters
- **Request/Response Inspection**: See raw JSON-RPC messages
- **Error Analysis**: Debug failed requests and responses
- **Real-time Monitoring**: Watch server behavior

### Test Scenarios with MCP Inspector

1. **Basic Write Test**
   ```json
   {
     "tool": "git_fs.write_and_commit",
     "arguments": {
       "repo": {"root": "/path/to/repo"},
       "path": "test.txt",
       "content": "Hello MCP!",
       "template": {
         "subject": "[{op}] {path} – {summary}",
         "body": "Test commit via MCP"
       }
     }
   }
   ```

2. **Read with History Test**
   ```json
   {
     "tool": "git_fs.read_with_history",
     "arguments": {
       "repo": {"root": "/path/to/repo"},
       "path": "test.txt",
       "history_limit": 5
     }
   }
   ```

3. **Reader Extract Test**
   ```json
   {
     "tool": "fs_reader.extract",
     "arguments": {
       "repo": {"root": "/path/to/repo"},
       "path": "test.txt",
       "query": "Hello",
       "before": 2,
       "after": 2
     }
   }
   ```

## Python SDK Testing

The fs-git MCP server can be tested using the Python MCP SDK.

### In-Memory Testing

```python
import asyncio
from mcp import Client
from mcp.server.fastmcp import FastMCP
from mcp_server.server_fastmcp_new import create_server

async def test_in_memory():
    """Test server in-memory without process overhead"""
    server = create_server()
    
    async with Client(server) as client:
        # Test server info
        info = await client.server_info()
        print(f"Server: {info.name} v{info.version}")
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {len(tools.tools)}")
        
        # Test git_fs.write_and_commit
        result = await client.call_tool(
            "git_fs.write_and_commit",
            {
                "repo": {"root": "/tmp/test_repo"},
                "path": "test.txt",
                "content": "Hello from MCP!",
                "template": {
                    "subject": "[{op}] {path} – {summary}",
                    "body": "Test commit"
                }
            }
        )
        print(f"Write result: {result.content}")

if __name__ == "__main__":
    asyncio.run(test_in_memory())
```

### Process-Based Testing

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_process_based():
    """Test server as separate process"""
    server_params = StdioServerParameters(
        command="fs-git-mcp",
        args=["serve", "--transport", "stdio"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize session
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            
            # Test specific tool
            result = await session.call_tool(
                "git_fs.read_with_history",
                {
                    "repo": {"root": "/tmp/test_repo"},
                    "path": "test.txt",
                    "history_limit": 3
                }
            )
            print(f"Read result: {result.content}")

if __name__ == "__main__":
    asyncio.run(test_process_based())
```

### Property-Based Testing with Hypothesis

```python
import asyncio
from hypothesis import given, strategies as st
from mcp import Client
from mcp_server.server_fastmcp_new import create_server

@given(
    content=st.text(min_size=1, max_size=100),
    path=st.text(min_size=1, max_size=20).map(lambda s: s.replace("/", "_") + ".txt")
)
async def test_write_various_content(content, path):
    """Test write_and_commit with various content"""
    server = create_server()
    
    async with Client(server) as client:
        result = await client.call_tool(
            "git_fs.write_and_commit",
            {
                "repo": {"root": "/tmp/test_repo"},
                "path": path,
                "content": content,
                "template": {
                    "subject": "[{op}] {path} – {summary}",
                    "body": "Property-based test"
                }
            }
        )
        
        # Verify result structure
        assert result.content
        assert isinstance(result.content, list)
        assert len(result.content) > 0
```

## End-to-End Protocol Testing

### JSON-RPC 2.0 Compliance Testing

```python
import json
import asyncio
import subprocess
from typing import Any, Dict

class MCPProtocolTester:
    def __init__(self, server_command: str):
        self.server_command = server_command
        self.process = None
        self.request_id = 0
    
    async def start_server(self):
        """Start MCP server process"""
        self.process = await asyncio.create_subprocess_exec(
            *self.server_command.split(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    
    async def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict:
        """Send JSON-RPC request and get response"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        return response
    
    async def test_protocol_compliance(self):
        """Test JSON-RPC 2.0 compliance"""
        await self.start_server()
        
        try:
            # Test initialize
            response = await self.send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            )
            assert response.get("jsonrpc") == "2.0"
            assert response.get("id") == 1
            assert "result" in response
            
            # Test list tools
            response = await self.send_request("tools/list")
            assert response.get("jsonrpc") == "2.0"
            assert response.get("id") == 2
            assert "result" in response
            assert "tools" in response["result"]
            
            # Test error handling
            response = await self.send_request("invalid_method")
            assert response.get("jsonrpc") == "2.0"
            assert "error" in response
            assert response["error"]["code"] == -32601  # Method not found
            
            print("✅ All protocol compliance tests passed")
            
        finally:
            self.process.terminate()
            await self.process.wait()

async def run_protocol_tests():
    tester = MCPProtocolTester("fs-git-mcp serve --transport stdio")
    await tester.test_protocol_compliance()

if __name__ == "__main__":
    asyncio.run(run_protocol_tests())
```

### Performance Testing

```python
import asyncio
import time
from mcp import Client
from mcp_server.server_fastmcp_new import create_server

async def test_performance():
    """Test server performance with concurrent requests"""
    server = create_server()
    
    async def make_request(i: int):
        start_time = time.time()
        async with Client(server) as client:
            result = await client.call_tool(
                "git_fs.read_with_history",
                {
                    "repo": {"root": "/tmp/test_repo"},
                    "path": f"test_{i}.txt",
                    "history_limit": 1
                }
            )
        end_time = time.time()
        return end_time - start_time
    
    # Test concurrent requests
    num_requests = 10
    start_time = time.time()
    
    tasks = [make_request(i) for i in range(num_requests)]
    durations = await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"Completed {num_requests} requests in {total_time:.2f}s")
    print(f"Average request time: {sum(durations)/len(durations):.3f}s")
    print(f"Requests per second: {num_requests/total_time:.2f}")

if __name__ == "__main__":
    asyncio.run(test_performance())
```

## Troubleshooting

### Common Issues

1. **Server Won't Start**
   ```bash
   # Check if command is available
   which fs-git-mcp
   
   # Try direct execution
   python -m mcp_server.server_fastmcp_new serve --transport stdio
   ```

2. **Import Errors**
   ```bash
   # Check Python path
   python -c "import mcp_server.server_fastmcp_new; print('OK')"
   
   # Reinstall if needed
   uv pip install -e .
   ```

3. **Permission Issues**
   ```bash
   # Check git repository permissions
   ls -la /path/to/repo/.git
   
   # Set git safe directory
   git config --global safe.directory /path/to/repo
   ```

4. **MCP Inspector Connection Issues**
   ```bash
   # Test with explicit command
   npx @modelcontextprotocol/inspector python -m mcp_server.server_fastmcp_new serve --transport stdio
   
   # Check Node.js version
   node --version  # Should be 16+
   ```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Enable JSON logging
export LOG_JSON=1

# Run server with debug
fs-git-mcp serve --transport stdio
```

### Test Repository Setup

```bash
# Create test repository
mkdir -p /tmp/fs-git-test
cd /tmp/fs-git-test
git init
git config user.email "test@example.com"
git config user.name "Test User"

# Create initial content
echo "# Test Repository" > README.md
git add README.md
git commit -m "Initial commit"
```

## Test Coverage

### Automated Tests

The project includes comprehensive test coverage:

- **Unit Tests**: 36 tests covering core functionality
- **Integration Tests**: MCP server protocol compliance
- **Acceptance Tests**: End-to-end workflow verification

### Running Tests

```bash
# Run all tests
make test

# Run specific test categories
make test-unit
make test-integration
make test-e2e

# Run with coverage
make test-coverage
```

### Manual Testing Checklist

- [ ] Server starts without errors
- [ ] All 12 MCP tools are discoverable
- [ ] Basic write/read operations work
- [ ] Staged workflow completes successfully
- [ ] Path authorization enforces rules
- [ ] Error handling provides useful messages
- [ ] MCP Inspector can connect and test tools
- [ ] JSON-RPC 2.0 protocol compliance
- [ ] Performance meets expectations (<100ms per request)

### Continuous Integration

The project uses GitHub Actions for automated testing:

```yaml
# .github/workflows/test.yml
name: Test MCP Server
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: uv pip install -e .[dev]
      - name: Run tests
        run: make test
      - name: Test MCP server
        run: |
          npx @modelcontextprotocol/inspector fs-git-mcp &
          sleep 5
          # Run MCP protocol tests
```

## Next Steps

1. **Automated MCP Testing**: Integrate MCP Inspector tests into CI/CD
2. **Load Testing**: Test performance under concurrent load
3. **Compatibility Testing**: Test with different MCP clients
4. **Security Testing**: Verify path authorization and input validation