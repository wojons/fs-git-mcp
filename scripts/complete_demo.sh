#!/bin/bash
# Complete fs-git CLI Demo - Copy and paste this entire script

set -e  # Exit on any error

echo "🚀 Starting fs-git CLI Demo..."

# 1) Setup and Installation
echo "📦 Step 1: Installation and setup"
cd /Users/lexykwaii/Code/anything-loop-tests/fs-git/repos/fs-git  # Adjust to your project directory
uv venv && uv pip install -e .[dev]
pre-commit install

# 2) Initialize sample repository
echo "🏗️ Step 2: Initialize sample repository"
# Assume scripts/init_sample_repo.sh exists, or create a simple one
mkdir -p tests/fixtures/repos/sample-a/src tests/fixtures/repos/sample-a/docs
cd tests/fixtures/repos/sample-a
git init
git config user.name "Demo User"
git config user.email "demo@example.com"
echo "# Sample Repo" > README.md
git add README.md
git commit -m "Initial commit"
cd -

# 3) Basic direct write operations
echo "✍️ Step 3: Direct write operations"
uv run fs-git write --repo tests/fixtures/repos/sample-a --path src/hello.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "seed hello" --reason "bootstrap" <<'EOF'
hello world
EOF

echo "📖 Reading file with history:"
uv run fs-git reader extract --repo tests/fixtures/repos/sample-a --path src/hello.txt --query "hello"

# 4) Staged workflow demonstration
echo "🔄 Step 4: Staged workflow"
sid=$(uv run fs-git staged start --repo tests/fixtures/repos/sample-a --ticket T-42 | jq -r .id || echo "demo-session")
echo "Started staged session: $sid"

uv run fs-git staged write --session "$sid" --path src/hello.txt --file - --summary "add exclamation" <<'EOF'
hello world!
EOF

echo "📋 Preview staged changes:"
uv run fs-git staged preview --session "$sid"

echo "🔀 Finalize staged session:"
uv run fs-git staged finalize --session "$sid" --strategy rebase-merge

# 5) Text replacement operations
echo "🔄 Step 5: Text replacement"
uv run fs-git replace --repo tests/fixtures/repos/sample-a --path src/hello.txt \
  --search "world" --replace "mcp" --commit --summary "rename subject"

# 6) Patch application
echo "🔧 Step 6: Apply patch"
cat > /tmp/patch.diff <<'EOF'
diff --git a/src/hello.txt b/src/hello.txt
index 1234567..abcdefg 100644
--- a/src/hello.txt
+++ b/src/hello.txt
@@ -1 +1 @@
-hello mcp!
+hello fs-git mcp!
EOF

uv run fs-git patch --repo tests/fixtures/repos/sample-a --path src/hello.txt --file /tmp/patch.diff --summary "apply demo patch"

# 7) Path authorization demonstration (new feature)
echo "🔒 Step 7: Path authorization"
# Create a test file in allowed path
uv run fs-git write --repo tests/fixtures/repos/sample-a --path docs/README.md \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "create docs" --reason "documentation" \
  --allow-paths "docs/**" <<'EOF'
# Documentation
This is allowed.
EOF

# Try to write to denied path (should fail)
echo "❌ Testing denied path (should fail):"
if uv run fs-git write --repo tests/fixtures/repos/sample-a --path forbidden.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "test denied" --reason "test" \
  --allow-paths "docs/**" --deny-paths "!forbidden.txt" <<'EOF'
test content
EOF; then
  echo "❌ Failed to block denied path"
  exit 1
else
  echo "✅ Correctly blocked denied path"
fi

# 8) MCP Server testing
echo "🌐 Step 8: MCP Server testing"
echo "Starting MCP server in background..."
uv run fs-git serve --transport stdio &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

echo "🧪 MCP server is running with PID: $SERVER_PID"
echo "Test with MCP Inspector: npx @modelcontextprotocol/inspector fs-git-mcp"

# Clean up
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

# 9) Environment variable configuration
echo "⚙️ Step 9: Environment variable configuration"
export FS_GIT_ALLOWED_PATHS="src/**,docs/**"
export FS_GIT_DENIED_PATHS="!**/node_modules/**,!**/.git/**"

uv run fs-git write --repo tests/fixtures/repos/sample-a --path src/config.json \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "add config" --reason "configuration" <<'EOF'
{"version": "1.0", "allowed": true}
EOF

echo "✅ Demo completed successfully!"
echo "📊 Final git log:"
cd tests/fixtures/repos/sample-a && git log --oneline -10
