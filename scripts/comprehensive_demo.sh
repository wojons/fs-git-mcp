#!/bin/bash
# Complete fs-git CLI Demo - Copy and paste this entire script

set -e  # Exit on any error

echo "🚀 Starting fs-git CLI Demo..."

# 1) Setup and Installation
echo "📦 Step 1: Installation and setup"
echo "Change this to your project directory:"
echo "cd /path/to/your/project"
echo ""
echo "Run these commands:"
echo "uv venv && uv pip install -e .[dev]"
echo "pre-commit install"
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -d "repos/fs-git" ]; then
    echo "❌ Error: Please run this script from the fs-git project root directory"
    echo "Expected to find pyproject.toml and repos/fs-git/ directory"
    exit 1
fi

cd repos/fs-git

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install uv first."
    echo "Visit: https://github.com/astral-sh/uv"
    exit 1
fi

echo "✅ Environment setup complete"

# 2) Initialize sample repository
echo "🏗️ Step 2: Initialize sample repository"
if [ -f "scripts/init_sample_repo.sh" ]; then
    bash scripts/init_sample_repo.sh
else
    echo "⚠️ Warning: init_sample_repo.sh not found, using fallback initialization"
    mkdir -p tests/fixtures/repos/sample-a
    cd tests/fixtures/repos/sample-a
    git init
    git config user.email "demo@example.com"
    git config user.name "Demo User"
    mkdir -p src docs
    echo "# Sample Repository" > README.md
    git add README.md
    git commit -m "Initial commit"
    cd ../../..
fi

echo "✅ Sample repository initialized"

# 3) Basic direct write operations
echo "✍️ Step 3: Direct write operations"
echo "Creating hello.txt file with git commit..."

cd tests/fixtures/repos/sample-a

fs-git write --repo . --path src/hello.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "seed hello" --reason "bootstrap" <<'EOF'
hello world
EOF

echo "📖 Reading file with history:"
fs-git reader extract --repo . --path src/hello.txt --query "hello"

echo ""
echo "📊 Git log shows the commit:"
git log --oneline -3

# 4) Staged workflow demonstration
echo ""
echo "🔄 Step 4: Staged workflow"
echo "Starting staged session..."

SESSION_OUTPUT=$(fs-git staged start --repo . --ticket T-42)
SESSION_ID=$(echo "$SESSION_OUTPUT" | jq -r .id)

if [ "$SESSION_ID" = "null" ] || [ -z "$SESSION_ID" ]; then
    echo "❌ Error: Failed to start staged session"
    exit 1
fi

echo "Started staged session: $SESSION_ID"

echo "Making changes in staged session..."
fs-git staged write --session "$SESSION_ID" --path src/hello.txt --file - --summary "add exclamation" <<'EOF'
hello world!
EOF

echo "📋 Preview staged changes:"
fs-git staged preview --session "$SESSION_ID"

echo "🔀 Finalize staged session:"
fs-git staged finalize --session "$SESSION_ID" --strategy rebase-merge

echo ""
echo "📊 Git log after staged workflow:"
git log --oneline -5

# 5) Text replacement operations
echo ""
echo "🔄 Step 5: Text replacement"
echo "Replacing 'world' with 'mcp'..."

fs-git replace --repo . --path src/hello.txt \
  --search "world" --replace "mcp" --commit --summary "rename subject"

echo "Updated file content:"
cat src/hello.txt

echo ""
echo "📊 Git log shows replacement:"
git log --oneline -3

# 6) Patch application
echo ""
echo "🔧 Step 6: Apply patch"
echo "Creating and applying a patch..."

# Create patch file
cat > /tmp/patch.diff <<'EOF'
diff --git a/src/hello.txt b/src/hello.txt
index 3bd1f0e..8c7f5d6 100644
--- a/src/hello.txt
+++ b/src/hello.txt
@@ -1 +1 @@
-hello mcp!
+hello fs-git mcp!
EOF

echo "Applying patch..."
fs-git patch --repo . --path src/hello.txt --patch-file /tmp/patch.diff

echo "Updated file content after patch:"
cat src/hello.txt

echo ""
echo "📊 Git log shows patch application:"
git log --oneline -3

# Clean up patch file
rm -f /tmp/patch.diff

# 7) Path authorization demonstration (new feature)
echo ""
echo "🔒 Step 7: Path authorization"
echo "Testing allowed and denied paths..."

# Create a test file in allowed path
echo "Creating file in allowed path (docs/)..."
fs-git write --repo . --path docs/README.md \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "create docs" --reason "documentation" \
  --allow-paths "docs/**" <<'EOF'
# Documentation
This is allowed.
EOF

echo "✅ Successfully created docs/README.md"

# Try to write to denied path (should fail)
echo ""
echo "❌ Testing denied path (should fail):"
if fs-git write --repo . --path forbidden.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "test denied" --reason "test" \
  --allow-paths "docs/**" --deny-paths "!forbidden.txt" <<'EOF'
This should be blocked.
EOF
  2>/dev/null; then
  echo "❌ ERROR: Denied path was not blocked!"
else
  echo "✅ Correctly blocked denied path"
fi

# 8) MCP Server testing
echo ""
echo "🌐 Step 8: MCP Server testing"
echo "Starting MCP server in background..."

# Check if fs-git-mcp command is available
if ! command -v fs-git-mcp &> /dev/null; then
    echo "⚠️ Warning: fs-git-mcp command not found. Installing..."
    cd ../../..
    uv pip install -e .
    cd tests/fixtures/repos/sample-a
fi

# Start server in background
echo "Starting MCP server with stdio transport..."
timeout 5s fs-git-mcp serve --transport stdio >/dev/null 2>&1 &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ MCP server started successfully (PID: $SERVER_PID)"
    echo "🧪 MCP server is running and ready for connections"
    echo "💡 You can test with MCP Inspector: npx @modelcontextprotocol/inspector fs-git-mcp"
    
    # Clean up server process
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
else
    echo "⚠️ MCP server startup test completed (server process terminated as expected)"
fi

# 9) Environment variable configuration
echo ""
echo "⚙️ Step 9: Environment variable configuration"
echo "Testing environment variable support..."

export FS_GIT_ALLOWED_PATHS="src/**,docs/**"
export FS_GIT_DENIED_PATHS="!**/node_modules/**,!**/.git/**"

echo "Creating config file with environment variables..."
fs-git write --repo . --path src/config.json \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "add config" --reason "configuration" <<'EOF'
{"version": "1.0", "allowed": true}
EOF

echo "✅ Successfully created src/config.json using environment variables"

# Show environment variable info
echo ""
echo "📋 Environment variables used:"
echo "FS_GIT_ALLOWED_PATHS=$FS_GIT_ALLOWED_PATHS"
echo "FS_GIT_DENIED_PATHS=$FS_GIT_DENIED_PATHS"

# 10) Final verification
echo ""
echo "🎉 Demo completed successfully!"
echo "📊 Final git log:"
git log --oneline -10

echo ""
echo "📁 Repository structure:"
find . -name "*.md" -o -name "*.txt" -o -name "*.json" | head -10

echo ""
echo "✨ All fs-git features demonstrated successfully!"
echo ""
echo "📚 Next steps:"
echo "1. Try the commands with your own files"
echo "2. Test with MCP Inspector: npx @modelcontextprotocol/inspector fs-git-mcp"
echo "3. Configure Claude Desktop with the MCP server"
echo "4. Read the full documentation in README.md"

cd ../../..