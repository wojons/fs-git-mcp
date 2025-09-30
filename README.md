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

Run the demo script:
```bash
make demo
```

## Development

- **Tests**: `make test`
- **Lint**: `make fmt && make lint`
- **E2E**: `make test-e2e`

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for module details.

## Tooling

See [TOOLING.md](TOOLING.md) for MCP schema and integrations.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).