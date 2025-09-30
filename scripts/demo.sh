#!/bin/bash

# Demo script for fs-git MCP server

set -e

echo "Initializing sample repo..."
bash scripts/init_sample_repo.sh

echo "Direct write..."
python -m mcp_server.cli.main write --repo tests/fixtures/repos/sample-a --path src/hello.txt --file - --op "add" --summary "seed hello" <<'EOF'
hello world
EOF

echo "Read with history..."
python -m mcp_server.cli.main reader extract --repo tests/fixtures/repos/sample-a --path src/hello.txt --query "hello"

echo "Staged flow..."
sid=$(python -m mcp_server.cli.main staged start --repo tests/fixtures/repos/sample-a --ticket T-42 | grep "Started session" | cut -d' ' -f3)
python -m mcp_server.cli.main staged write --session "$sid" --repo tests/fixtures/repos/sample-a --path src/hello.txt --file - --summary "add exclamation" <<'EOF'
hello world!
EOF
python -m mcp_server.cli.main staged preview --session "$sid"
python -m mcp_server.cli.main staged finalize --session "$sid" --strategy rebase-merge

echo "Replace + commit..."
python -m mcp_server.cli.main replace --repo tests/fixtures/repos/sample-a --path src/hello.txt --search "world" --replace "mcp" --commit --summary "rename subject"

echo "Demo completed."