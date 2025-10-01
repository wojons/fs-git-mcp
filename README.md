# FS-Git MCP Server

A Git-enforced filesystem MCP server that integrates git with filesystem operations, enforcing commits on writes, providing reads with history, and supporting staged branching.

## Features

- **Direct Mode**: Write and commit in one call with templated messages.
- **Staged Mode**: Open ephemeral branch, stage edits, preview, then merge/rebase or abort.
- **Reader Subagent**: Intent-directed extraction and summarization.
- **Integrated Tools**: Wraps file_system, text_replace, code_diff with git semantics.
- **Safety**: Path traversal protection, git safe.directory, dirty tree guards.

## Installation

```bash
uv venv && uv pip install -e .[dev]
pre-commit install
```

## MCP Server Usage

### Running the MCP Server

The fs-git MCP server can be run in two ways:

**Option 1: Using the CLI command**
```bash
# For Claude Desktop and MCP Inspector (stdio transport)
fs-git serve

# For development/testing (TCP transport)  
fs-git serve --transport tcp --port 8080
```

**Option 2: Using the direct MCP server command**
```bash
# stdio mode (default, for Claude Desktop)
fs-git-mcp

# TCP mode for development
fs-git-mcp --transport tcp --port 8080
```

**Option 3: Using uvx (no installation required)**
```bash
# Run directly without installation
uvx fs-git-mcp

# Or with the CLI
uvx --from . fs-git serve
```

### Claude Desktop Configuration

Add this to your Claude Desktop configuration (`~/.claude/config.json`):

```json
{
  "mcpServers": {
    "fs-git": {
      "command": "uvx",
      "args": ["fs-git-mcp"]
    }
  }
}
```

Or if installed locally:
```json
{
  "mcpServers": {
    "fs-git": {
      "command": "fs-git-mcp"
    }
  }
}
```

### Testing with MCP Inspector

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Test the server
npx @modelcontextprotocol/inspector fs-git-mcp
```

### Available MCP Tools

The MCP server exposes these tool namespaces:

- **git_fs**: `write_and_commit`, `read_with_history`, `start_staged`, `staged_write`, `staged_preview`, `finalize_staged`, `abort_staged`
- **fs_reader**: `extract`, `answer_about_file` 
- **fs_text_replace**: `replace_and_commit`
- **fs_code_diff**: `preview_diff`
- **fs_io**: `read_file`, `stat_file`, `list_dir`, `make_dir`

## Path Authorization

FS-Git supports configurable path authorization for security. You can restrict which paths can be accessed using CLI parameters or environment variables.

### CLI Parameters

```bash
# Allow only specific paths
fs-git write --repo <root> --path src/utils.py \
  --allow-paths "src/**,docs/**" \
  --deny-paths "!src/secrets/**,!**/node_modules/**" \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "utility functions" <<'EOF'
def helper():
    return "utility"
EOF
```

### Environment Variables

Set path patterns via environment variables for global configuration:

```bash
# Set allowed paths (comma-separated)
export FS_GIT_ALLOWED_PATHS="src/**,docs/**,*.md"

# Set denied paths (comma-separated, with ! prefix)
export FS_GIT_DENIED_PATHS="!**/node_modules/**,!**/.git/**,!src/secrets/**"

# Now all fs-git commands will use these patterns
fs-git write --repo <root> --path src/app.py --file - --subject "Add app" <<'EOF'
print("Hello World")
EOF
```

### Pattern Support

- **Glob patterns**: `src/**`, `docs/**/*.md`, `*.txt`
- **Regex patterns**: `r".*\.py$"`, `r".*\.js$"`
- **Deny patterns**: Prefix with `!` (e.g., `!**/node_modules/**`)
- **Absolute paths**: `/etc/hosts`, `/usr/local/bin/`
- **Relative paths**: `src/`, `./docs/`

**Priority**: CLI parameters override environment variables.

## Quick Start

1. Initialize a repo:
   ```bash
   fs-git init <repo_root>
   ```

2. Direct write:
   ```bash
   fs-git write --repo <root> --path <p> --file <in> \
     --subject "[{op}] {path} – {summary}" --op "edit" --summary "update"
   ```

3. Staged flow:
   ```bash
   sid=$(fs-git staged start --repo <root> --ticket T-123)
   fs-git staged write --session "$sid" --path <p> --file <in> --summary "..."
   fs-git staged preview --session "$sid"
   fs-git staged finalize --session "$sid" --strategy rebase-merge
   ```

4. Reader extract:
   ```bash
   fs-git reader extract --repo <root> --path <p> --query "foo.*bar" --regex
   ```

## Demo

### Quick Demo
Run the basic demo script:
```bash
make demo
```

### Comprehensive Demo
Run the complete copy-paste demo that showcases all features:
```bash
# From the fs-git project root
bash repos/fs-git/scripts/comprehensive_demo.sh
```

This comprehensive demo includes:
- Installation and setup
- Basic direct write operations with git commits
- Staged workflow with ephemeral branches
- Text replacement and patch application
- Path authorization with allowed/denied patterns
- Environment variable configuration
- MCP server testing
- Claude Desktop integration examples

## Development

- **Tests**: `make test`
- **Lint**: `make fmt && make lint`
- **E2E**: `make test-e2e`

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for module details.

## Tooling

See [TOOLING.md](TOOLING.md) for MCP schema and integrations.

## Troubleshooting

### Common Issues

- **Import Errors**: Ensure `mcp_server` is in PYTHONPATH or installed with `uv pip install -e .`
- **Git Safe Directory**: If git complains about unsafe repo, run `git config --global --add safe.directory <repo_root>`
- **Path Authorization Denied**: Check your `FS_GIT_ALLOWED_PATHS` and `FS_GIT_DENIED_PATHS` env vars or CLI flags.
- **Staged Session Not Found**: Sessions are stored in `~/.fs_git_sessions`. Clear if corrupted.
- **MCP Inspector Connection**: Use `fs-git serve` for stdio mode with Inspector. For TCP, use `--transport tcp`.
- **Subprocess Python Errors**: Tests use `sys.executable` to match your Python environment.

### Logs

- Server logs: Check `server.log` or stderr.
- Git logs: Use `git log --oneline -10` in repo.

### Debug Mode

Run with debug:
```bash
FS_GIT_DEBUG=true fs-git serve --transport tcp
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).