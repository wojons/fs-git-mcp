#!/bin/bash

# Initialize sample repo for demo

set -e

REPO_DIR="tests/fixtures/repos/sample-a"

# Create directory if it doesn't exist
mkdir -p "$REPO_DIR"

# Initialize git repo if needed
cd "$REPO_DIR"
if [ ! -d .git ]; then
    git init
    git config user.name "Test User"
    git config user.email "test@example.com"
    
    # Create initial README
    echo "# Sample Repository

This is a sample repository for fs-git MCP testing and demos." > README.md
    git add README.md
    git commit -m "Initial commit"
    
    echo "Sample repository initialized at $REPO_DIR"
else
    echo "Sample repository already exists at $REPO_DIR"
    git checkout main || true
fi