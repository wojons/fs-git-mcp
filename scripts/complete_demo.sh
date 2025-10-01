#!/bin/bash
# Complete fs-git CLI Demo - Updated with all fixes and features

set -e  # Exit on any error

echo "🚀 Starting fs-git CLI Demo..."

# Prerequisites: Ensure you're in the project root and have installed dependencies
# cd /path/to/fs-git
# uv venv && uv pip install -e .[dev]
# pre-commit install

# 1. Initialize sample repository if not exists
echo "🏗️ Step 1: Initialize sample repository"
REPO_DIR="tests/fixtures/repos/sample-a"
if [ ! -d "$REPO_DIR" ]; then
    mkdir -p "$REPO_DIR"
    fs-git init "$REPO_DIR"
    cd "$REPO_DIR"
    echo "Initial file" > initial.txt
    git add initial.txt && git commit -m "Initial commit"
    cd - > /dev/null
fi

# 2. Basic direct write operations
echo "✍️ Step 2: Direct write operations"
fs-git write --repo "$REPO_DIR" --path src/hello.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "seed hello world" --reason "bootstrap project" <<'EOF'
Hello, fs-git MCP!
This is a direct write and commit.
EOF

echo "📖 Step 3: Read with history"
fs-git read --repo "$REPO_DIR" --path src/hello.txt

# 4. Reader subagent extraction
echo "🔍 Step 4: Reader extraction"
fs-git reader extract --repo "$REPO_DIR" --path src/hello.txt --query "MCP" --before 1 --after 1

# 5. Answer about file
echo "❓ Step 5: Answer about file"
fs-git reader answer --repo "$REPO_DIR" --path src/hello.txt --question "What is the main content of this file?"

# 6. Staged workflow demonstration
echo "🔄 Step 6: Staged workflow"
SID=$(fs-git staged start --repo "$REPO_DIR" --ticket "DEMO-001" | jq -r '.id' 2>/dev/null || echo "demo-session-001")
echo "Started staged session: $SID"

# Write to staged branch
fs-git staged write --session "$SID" --repo "$REPO_DIR" --path src/hello.txt \
  --file - --summary "add version info" <<'EOF'
Hello, fs-git MCP v1.0!
This is a staged edit.
EOF

# Preview changes
echo "📋 Step 7: Preview staged changes"
fs-git staged preview --session "$SID"

# Finalize
echo "🔀 Step 8: Finalize staged session"
fs-git staged finalize --session "$SID" --strategy "merge-ff"

# 9. Text replacement
echo "🔄 Step 9: Text replacement with commit"
fs-git replace --repo "$REPO_DIR" --path src/hello.txt \
  --search "v1.0" --replace "v2.0" --commit --summary "update version"

# 10. Apply patch
echo "🔧 Step 10: Apply patch"
cat > /tmp/demo-patch.diff <<'EOF'
diff --git a/src/hello.txt b/src/hello.txt
index abc123..def456 100644
--- a/src/hello.txt
+++ b/src/hello.txt
@@ -1,2 +1,2 @@
-Hello, fs-git MCP v2.0!
-This is a staged edit.
+Hello, fs-git MCP v2.0 - Patched!
+This is a staged edit with patch applied.
EOF

fs-git patch --repo "$REPO_DIR" --path src/hello.txt --file /tmp/demo-patch.diff --summary "apply demo patch"

# 11. Path authorization demonstration
echo "🔒 Step 11: Path authorization"
# Allowed path
fs-git write --repo "$REPO_DIR" --path docs/welcome.md \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "create welcome doc" --allow-paths "docs/**" <<'EOF'
# Welcome to fs-git MCP
This is in the allowed docs directory.
EOF

# Denied path attempt (should fail)
echo "❌ Step 12: Test denied path (expect failure)"
if fs-git write --repo "$REPO_DIR" --path secret.txt \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "secret file" --allow-paths "docs/**" --deny-paths "!secret.txt" <<'EOF'
Secret content
EOF; then
  echo "❌ Error: Denied path write succeeded unexpectedly"
  exit 1
else
  echo "✅ Correctly blocked denied path"
fi

# Environment variables demo
echo "⚙️ Step 13: Environment variable configuration"
export FS_GIT_ALLOWED_PATHS="src/**,docs/**"
export FS_GIT_DENIED_PATHS="!**/secrets/**,!**/.git/**"

# Write to allowed path via env
fs-git write --repo "$REPO_DIR" --path src/config.py \
  --file - --subject "[{op}] {path} – {summary}" \
  --op "add" --summary "add config" <<'EOF'
# Configuration file
ALLOWED_PATHS = "src/**, docs/**"
EOF

echo "📊 Step 14: Show final git log"
cd "$REPO_DIR" && git log --oneline -10

echo "✅ Complete demo finished successfully!"
rm -f /tmp/demo-patch.diff