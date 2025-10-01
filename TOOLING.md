# Tooling

## MCP Namespaces

### git_fs

- `write_and_commit(WriteRequest) -> WriteResult`
- `read_with_history(repo, path, history_limit?) -> ReadResult`
- `start_staged(repo, ticket?, template?): StagedSession`
- `staged_write(session_id, WriteRequest) -> WriteResult`
- `staged_preview(session_id) -> Preview`
- `finalize(session_id, FinalizeOptions) -> {merged_sha, base_branch}`
- `abort(session_id) -> {status}`

### fs_reader

- `extract(ReadIntent) -> ReadResult`
- `answer_about_file(repo, path, question, ...) -> {answer, citations}`

### fs_text_replace

- `replace_and_commit(repo, path, search, replace, regex?, template) -> WriteResult`
- `batch_replace_and_commit(...) -> {results}`

### fs_code_diff

- `preview_diff(repo, path, modified_content, ...) -> {diff}`
- `apply_patch_and_commit(repo, path, patch, template, staged?) -> WriteResult`

### fs_io

- `read(repo, path) -> string`
- `stat(repo, path) -> {...}`
- `ls(repo, path, recursive?) -> string[]`
- `mkdir(repo, path, recursive?) -> {ok}`

## Schema

See code for Pydantic models.

## Testing MCP Protocol

### Using MCP Inspector

1. Install MCP Inspector:
   ```bash
   npm install -g @modelcontextprotocol/inspector
   ```

2. Run the server:
   ```bash
   fs-git serve --transport stdio
   ```

3. Test with Inspector:
   ```bash
   npx @modelcontextprotocol/inspector fs-git-mcp
   ```

   Or if using uvx:
   ```bash
   npx @modelcontextprotocol/inspector --command uvx --args fs-git-mcp
   ```

### Python SDK Testing

Use the MCP Python SDK for programmatic testing:

```python
from mcp import Client
from mcp.server.fastmcp import FastMCP

# In-memory testing
server = FastMCP("test")
# Add tools...
client = Client(server)
result = await client.call_tool("write_and_commit", {"repo": {"root": "/tmp/test"}, "path": "test.txt", "content": "test"})
print(result)

# Process-based testing
from mcp.testing import run_server_in_process
async with run_server_in_process("fs-git-mcp", transport="stdio"):
    # Test client interactions
    pass
```

### End-to-End MCP Testing

The test suite includes comprehensive MCP protocol tests:

- **test_mcp_server.py**: Tests all 12 tools via JSON-RPC
- **test_mcp_integration.py**: CLI to MCP server integration
- **test_protocol_compliance.py**: JSON-RPC error handling, batch calls

Run with:
```bash
pytest tests/test_mcp_server.py -v
make test-mcp
```

### Real MCP Client Examples

#### Claude Desktop

Configure in `~/.claude/config.json`:
```json
{
  "mcpServers": {
    "fs-git": {
      "command": "fs-git-mcp",
      "args": ["serve", "--transport", "stdio"]
    }
  }
}
```

#### Custom Python Client

```python
import asyncio
from mcp import Client
from mcp.types import ToolResult

async def test_fs_git():
    # Connect to TCP server
    client = Client("ws://localhost:8080")
    await client.initialize()
    
    # List tools
    tools = await client.list_tools()
    assert "write_and_commit" in [t.name for t in tools.tools]
    
    # Call tool
    result = await client.call_tool(
        "write_and_commit",
        {
            "repo": {"root": "/tmp/test-repo"},
            "path": "example.txt",
            "content": "Hello MCP!",
            "op": "add",
            "summary": "test write"
        }
    )
    assert isinstance(result, ToolResult)
    assert "commit_sha" in result.content

asyncio.run(test_fs_git())
```

## CLI-Based MCP Clients for Debugging

For shell-based debugging, use these tools:

### mcp-cli (from MCP SDK)

```bash
pip install mcp[cli]
mcp-cli --server fs-git-mcp list-tools
mcp-cli --server fs-git-mcp call-tool write_and_commit '{"repo": {"root": "/tmp/repo"}, "path": "test.txt", "content": "test"}'
```

### netcat for TCP Debugging

```bash
# Start server in TCP mode
fs-git serve --transport tcp --port 8080

# Send JSON-RPC request via netcat
echo '{"jsonrpc": "2.0", "id": 1, "method": "list_tools", "params": {}}' | nc localhost 8080
```

### MCP Inspector CLI Mode

```bash
# Run Inspector in CLI mode for scripted testing
npx @modelcontextprotocol/inspector fs-git-mcp --headless --test list_tools
```

## Shell Environment Debug Tools

Integrate these for automated MCP testing in CI/CD:

### expect (for interactive testing)

```bash
# Test server startup and tool call
expect -c '
spawn fs-git serve --transport stdio
expect "Starting"
send "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"list_tools\",\"params\":{}}\n"
expect "result"
send "\n"
expect eof
'
```

### MCP Testing Harness (Custom Script)

Create `scripts/test_mcp_harness.sh`:
```bash
#!/bin/bash
# Run MCP server and test with curl/netcat

fs-git serve --transport tcp --port 8080 &
SERVER_PID=$!
sleep 2

# Test list_tools
echo '{"jsonrpc": "2.0", "id": 1, "method": "list_tools", "params": {}}' | nc localhost 8080 | jq .

kill $SERVER_PID
```

## Context7 Documentation Access

Use the context7 tools to access MCP docs:

- `resolve_library_id(libraryName="modelcontextprotocol/inspector")` for Inspector docs
- `get_library_docs(context7CompatibleLibraryID="/modelcontextprotocol/inspector", topic="testing")` for testing guides
- `get_library_docs(context7CompatibleLibraryID="/modelcontextprotocol_io_specification", topic="json-rpc")` for protocol spec

## Automated MCP Testing Pipeline

1. **Unit Tests**: `pytest tests/unit/`
2. **MCP Protocol Tests**: `pytest tests/test_mcp_server.py`
3. **Integration Tests**: `pytest tests/test_mcp_integration.py`
4. **E2E with Inspector**: `make test-inspector`
5. **Claude Desktop Sim**: `scripts/test_claude_config.sh`

Run full pipeline:
```bash
make test-full
```

This ensures 100% MCP protocol compliance and tool functionality.