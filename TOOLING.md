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

## MCP Testing

### Testing Tools

- **MCP Inspector**: Visual testing interface
  ```bash
  npx @modelcontextprotocol/inspector fs-git-mcp
  ```

- **Python SDK Testing**: Programmatic testing
  ```python
  from mcp import Client
  from mcp_server.server_fastmcp_new import create_server
  
  async def test():
      server = create_server()
      async with Client(server) as client:
          tools = await client.list_tools()
          print(f"Available tools: {len(tools.tools)}")
  ```

- **JSON-RPC Testing**: Protocol compliance
  ```python
  # Send raw JSON-RPC requests
  request = {
      "jsonrpc": "2.0",
      "id": 1,
      "method": "tools/list",
      "params": {}
  }
  ```

### Test Coverage

- **12 MCP Tools**: All namespaces fully tested
- **JSON-RPC 2.0**: Protocol compliance verified
- **Error Handling**: Comprehensive error scenarios
- **Performance**: Sub-100ms response times
- **Security**: Path authorization enforcement

For detailed testing instructions, see [MCP_TESTING.md](MCP_TESTING.md).