#!/bin/bash

# Demo script for fs-git MCP server

set -e

echo "=== FS-Git MCP Demo ==="

# Create a temporary directory for the demo
DEMO_DIR=$(mktemp -d -t fs_git_demo_XXXXXX)
echo "Demo directory: $DEMO_DIR"

# Initialize git repo
cd "$DEMO_DIR"
git init
git config user.name "Demo User"
git config user.email "demo@example.com"

# Create initial README
echo "# Demo Repository

This is a demo repository for fs-git MCP functionality." > README.md
git add README.md
git commit -m "Initial commit"

echo ""
echo "=== 1. Direct Write ==="

# Test direct write
fs-git write --repo "$DEMO_DIR" --path hello.txt --op add --summary "seed hello" <<'EOF'
hello world
EOF

# Read the file
echo "File content:"
cat hello.txt

echo ""
echo "Git log:"
git log --oneline -1

echo ""
echo "=== 2. Reader Extract ==="

# Test reader extract
fs-git reader extract --repo "$DEMO_DIR" --path hello.txt --query "hello"

echo ""
echo "=== 3. Staged Workflow ==="

# Start staged session
SESSION_ID=$(fs-git staged start --repo "$DEMO_DIR" --ticket T-42 | awk '{print $NF}')
echo "Session ID: $SESSION_ID"

# Staged write
fs-git staged write --session "$SESSION_ID" --repo "$DEMO_DIR" --path staged.txt --summary "add exclamation" <<'EOF'
hello world!
EOF

# Preview changes
echo "Preview:"
fs-git staged preview --session "$SESSION_ID"

# Finalize
fs-git staged finalize --session "$SESSION_ID" --strategy rebase-merge

echo "Final result:"
cat staged.txt
git log --oneline -1

echo ""
echo "=== 4. Replace and Commit ==="

# Create a file to replace
echo "Hello, World!" > replace.txt
git add replace.txt
git commit -m "Add replace test file"

# Replace text
fs-git replace --repo "$DEMO_DIR" --path replace.txt --search "World" --replace "MCP" --commit --summary "rename subject"

echo "After replacement:"
cat replace.txt
git log --oneline -1

echo ""
echo "=== 5. Safety Check ==="

# Test path traversal prevention (should fail)
echo "Testing path traversal..."
if fs-git write --repo "$DEMO_DIR" --path ../outside.txt --op add --summary "path traversal test" 2>/dev/null; then
    echo "ERROR: Path traversal was not prevented!"
else
    echo "✓ Path traversal correctly prevented"
fi

echo ""
echo "=== Demo Complete ==="
echo "Demo files are in: $DEMO_DIR"
echo "To cleanup: rm -rf $DEMO_DIR"