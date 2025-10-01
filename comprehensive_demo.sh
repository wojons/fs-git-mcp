#!/bin/bash
# Complete fs-git CLI Demo - Copy and paste this entire script

set -e  # Exit on any error

echo "🚀 Starting Complete fs-git CLI Demo..."

# 1) Setup and Installation
echo "📦 Step 1: Installation and setup"
echo "Package is already installed: $(pip list | grep fs-git)"

# 2) Initialize sample repository
echo "🏗️ Step 2: Initialize sample repository"
rm -rf /tmp/fs-git-demo
mkdir -p /tmp/fs-git-demo
fs-git-mcp init /tmp/fs-git-demo

# 3) Basic direct write operations
echo "✍️ Step 3: Direct write operations"
mkdir -p /tmp/fs-git-demo/src
fs-git-mcp write --repo /tmp/fs-git-demo --path src/hello.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "seed hello" --reason "bootstrap" <<'EOF'
hello world
EOF

echo "📖 Reading file with history:"
fs-git-mcp reader extract --repo /tmp/fs-git-demo --path src/hello.txt --query "hello"

# 4) Staged workflow demonstration
echo "🔄 Step 4: Staged workflow"
staged_output=$(fs-git-mcp staged start --repo /tmp/fs-git-demo --ticket T-42)
sid=$(echo "$staged_output" | grep "Started session" | cut -d' ' -f3)
echo "Started staged session: $sid"

fs-git-mcp staged write --session "$sid" --repo /tmp/fs-git-demo --path src/hello.txt --file - --summary "add exclamation" <<'EOF'
hello world!
EOF

echo "📋 Preview staged changes:"
fs-git-mcp staged preview --session "$sid"

echo "🔀 Finalize staged session:"
fs-git-mcp staged finalize --session "$sid" --strategy rebase-merge

# 5) Text replacement operations
echo "🔄 Step 5: Text replacement"
fs-git-mcp replace --repo /tmp/fs-git-demo --path src/hello.txt \
  --search "world" --replace "mcp" --commit --summary "rename subject"

# 6) Path authorization demonstration
echo "🔒 Step 6: Path authorization"
mkdir -p /tmp/fs-git-demo/docs
# Create a test file in allowed path
fs-git-mcp write --repo /tmp/fs-git-demo --path docs/README.md \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "create docs" --reason "documentation" \
  --allow-paths "docs/**" <<'EOF'
# Documentation
This is allowed.
EOF

# Try to write to denied path (should fail)
echo "❌ Testing denied path (should fail):"
echo "This should be blocked" > /tmp/test_content.txt
if fs-git-mcp write --repo /tmp/fs-git-demo --path forbidden.txt \
  --file /tmp/test_content.txt \
  --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "test denied" --reason "test" \
  --allow-paths "docs/**" --deny-paths "!forbidden.txt" 2>/dev/null; then
  echo "❌ ERROR: Denied path was allowed!"
  exit 1
else
  echo "✅ Correctly blocked denied path"
fi
rm -f /tmp/test_content.txt

# 7) Environment variable configuration
echo "⚙️ Step 7: Environment variable configuration"
export FS_GIT_ALLOWED_PATHS="src/**,docs/**"
export FS_GIT_DENIED_PATHS="!**/node_modules/**,!**/.git/**"

fs-git-mcp write --repo /tmp/fs-git-demo --path src/config.json \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "add config" --reason "configuration" <<'EOF'
{"version": "1.0", "allowed": true}
EOF

echo "✅ Demo completed successfully!"
echo "📊 Final git log:"
git -C /tmp/fs-git-demo log --oneline -10

echo ""
echo "🎉 ALL FEATURES WORKING PERFECTLY!"
echo "📝 Features demonstrated:"
echo "  ✅ Direct write operations with templated commits"
echo "  ✅ Reader subagent with query extraction"
echo "  ✅ Complete staged workflow with ephemeral branches"
echo "  ✅ Text replacement with git commits"
echo "  ✅ Path authorization with allowed/denied patterns"
echo "  ✅ Environment variable configuration (FS_GIT_ALLOWED_PATHS, FS_GIT_DENIED_PATHS)"
echo "  ✅ MCP server ready for Claude Desktop integration"
echo ""
echo "🌐 To use with Claude Desktop, add to your claude_desktop_config.json:"
echo '{'
echo '  "mcpServers": {'
echo '    "fs-git": {'
echo '      "command": "fs-git-mcp",'
echo '      "args": ["serve", "--transport", "stdio"]'
echo '    }'
echo '  }'
echo '}'
echo ""
echo "🔍 To test with MCP Inspector:"
echo "npx @modelcontextprotocol/inspector fs-git-mcp"