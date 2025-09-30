#!/usr/bin/env python3
"""
Comprehensive test script to verify fs-git MCP functionality.
This script tests all major features end-to-end.
"""

import tempfile
import subprocess
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

def run_command(cmd: List[str], cwd: str = None, capture_output: bool = True, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    if cwd:
        print(f"  in directory: {cwd}")
    
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            capture_output=capture_output, 
            text=True, 
            check=True,
            input=input_text
        )
        if capture_output:
            print(f"  stdout: {result.stdout[:200]}...")
        return result
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: {e}")
        if capture_output and e.stderr:
            print(f"  stderr: {e.stderr}")
        return e

def create_test_repo() -> str:
    """Create a test git repository."""
    temp_dir = tempfile.mkdtemp(prefix="fs_git_test_")
    print(f"Creating test repo in: {temp_dir}")
    
    # Initialize git repo
    run_command(["git", "init"], cwd=temp_dir)
    run_command(["git", "config", "user.name", "Test User"], cwd=temp_dir)
    run_command(["git", "config", "user.email", "test@example.com"], cwd=temp_dir)
    
    # Create initial README
    readme_path = Path(temp_dir) / "README.md"
    readme_path.write_text("# Test Repository\n\nThis is a test repository for fs-git MCP.\n")
    run_command(["git", "add", "README.md"], cwd=temp_dir)
    run_command(["git", "commit", "-m", "Initial commit"], cwd=temp_dir)
    
    return temp_dir

def test_basic_write(repo_dir: str) -> Dict[str, Any]:
    """Test basic write functionality."""
    print("\n=== Testing Basic Write ===")
    
    # Test direct write
    result = run_command([
        "fs-git", "write", 
        "--repo", repo_dir,
        "--path", "test.txt",
        "--op", "add",
        "--summary", "test file creation"
    ], input_text="Hello, World!\n")
    
    if result.returncode != 0:
        return {"success": False, "error": str(result)}
    
    # Verify file exists
    test_file = Path(repo_dir) / "test.txt"
    if not test_file.exists():
        return {"success": False, "error": "File was not created"}
    
    # Verify content
    content = test_file.read_text()
    if content != "Hello, World!\n":
        return {"success": False, "error": f"File content mismatch: {content}"}
    
    # Verify git commit
    log_result = run_command(["git", "log", "--oneline", "-1"], cwd=repo_dir)
    if "[add] test.txt – test file creation" not in log_result.stdout:
        return {"success": False, "error": "Commit message incorrect"}
    
    return {"success": True}

def test_staged_workflow(repo_dir: str) -> Dict[str, Any]:
    """Test staged workflow."""
    print("\n=== Testing Staged Workflow ===")
    
# Start staged session
    result = run_command([
        "fs-git", "staged", "start",
        "--repo", repo_dir,
        "--ticket", "T-123"
    ])
    
    if result.returncode != 0:
        return {"success": False, "error": f"Failed to start staged session: {result}"}
    
    # Extract session ID from output
    session_id = result.stdout.strip().split()[-1]  # Get last word from "Started session <id>"
    
    # Staged write
    result = run_command([
        "fs-git", "staged", "write",
        "--session", session_id,
        "--repo", repo_dir,
        "--path", "staged.txt",
        "--summary", "staged file creation"
    ], input_text="Staged content\n")
    
    if result.returncode != 0:
        return {"success": False, "error": f"Staged write failed: {result}"}
    
    # Preview changes
    result = run_command([
        "fs-git", "staged", "preview",
        "--session", session_id
    ])
    
    if result.returncode != 0:
        return {"success": False, "error": f"Staged preview failed: {result}"}
    
    # Finalize session
    result = run_command([
        "fs-git", "staged", "finalize",
        "--session", session_id,
        "--strategy", "merge-ff"
    ])
    
    if result.returncode != 0:
        return {"success": False, "error": f"Staged finalize failed: {result}"}
    
    # Verify file exists in main branch
    staged_file = Path(repo_dir) / "staged.txt"
    if not staged_file.exists():
        return {"success": False, "error": "Staged file not found after finalization"}
    
    return {"success": True}

def test_reader_functionality(repo_dir: str) -> Dict[str, Any]:
    """Test reader functionality."""
    print("\n=== Testing Reader Functionality ===")
    
    # Create a test file with known content
    test_file = Path(repo_dir) / "code.py"
    test_content = '''#!/usr/bin/env python3

def hello():
    """Say hello to the world."""
    print("Hello, World!")

def add(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    def __init__(self):
        self.value = 0
    
    def increment(self):
        self.value += 1
        return self.value
'''
    test_file.write_text(test_content)
    
    # Commit the file
    run_command(["git", "add", "code.py"], cwd=repo_dir)
    run_command(["git", "commit", "-m", "Add Python code file"], cwd=repo_dir)
    
    # Test reader extract
    result = run_command([
        "fs-git", "reader", "extract",
        "--repo", repo_dir,
        "--path", "code.py",
        "--query", "def hello",
        "--before", "1",
        "--after", "2"
    ])
    
    if result.returncode != 0:
        return {"success": False, "error": f"Reader extract failed: {result}"}
    
    if "def hello():" not in result.stdout:
        return {"success": False, "error": "Reader extract didn't find expected content"}
    
    # Test reader answer
    result = run_command([
        "fs-git", "reader", "answer",
        "--repo", repo_dir,
        "--path", "code.py",
        "--question", "What functions are defined in this file?"
    ])
    
    if result.returncode != 0:
        return {"success": False, "error": f"Reader answer failed: {result}"}
    
    return {"success": True}

def test_replace_functionality(repo_dir: str) -> Dict[str, Any]:
    """Test text replace functionality."""
    print("\n=== Testing Replace Functionality ===")
    
    # Create a test file
    test_file = Path(repo_dir) / "replace_test.txt"
    test_file.write_text("Hello, World!\nThis is a test file.\n")
    
    # Commit the file
    run_command(["git", "add", "replace_test.txt"], cwd=repo_dir)
    run_command(["git", "commit", "-m", "Add replace test file"], cwd=repo_dir)
    
    # Test replace and commit
    result = run_command([
        "fs-git", "replace",
        "--repo", repo_dir,
        "--path", "replace_test.txt",
        "--search", "World",
        "--replace", "MCP",
        "--commit",
        "--summary", "Replace World with MCP"
    ])
    
    if result.returncode != 0:
        return {"success": False, "error": f"Replace failed: {result}"}
    
    # Verify replacement
    content = test_file.read_text()
    if "Hello, MCP!" not in content:
        return {"success": False, "error": "Replacement not found in file"}
    
    # Verify commit was created
    log_result = run_command(["git", "log", "--oneline", "-1"], cwd=repo_dir)
    if "Replace World with MCP" not in log_result.stdout:
        return {"success": False, "error": "Replace commit not found"}
    
    return {"success": True}

def test_safety_mechanisms(repo_dir: str) -> Dict[str, Any]:
    """Test safety mechanisms."""
    print("\n=== Testing Safety Mechanisms ===")
    
    # Test path traversal prevention
    result = run_command([
        "fs-git", "write",
        "--repo", repo_dir,
        "--path", "../outside.txt",
        "--op", "add",
        "--summary", "path traversal test"
    ], input_text="This should fail\n")
    
    if result.returncode == 0:
        return {"success": False, "error": "Path traversal was not prevented"}
    
    # Test invalid template (missing required tokens)
    result = run_command([
        "fs-git", "write",
        "--repo", repo_dir,
        "--path", "invalid.txt",
        "--subject", "Invalid template missing tokens",
        "--op", "add",
        "--summary", "should fail"
    ], input_text="This should fail due to invalid template\n")
    
    if result.returncode == 0:
        return {"success": False, "error": "Invalid template was not rejected"}
    
    return {"success": True}

def run_comprehensive_tests():
    """Run all comprehensive tests."""
    print("Starting comprehensive fs-git MCP tests...")
    
    # Create test repository
    repo_dir = create_test_repo()
    
    # Track test results
    test_results = []
    
    # Run all tests
    tests = [
        ("Basic Write", test_basic_write),
        ("Staged Workflow", test_staged_workflow),
        ("Reader Functionality", test_reader_functionality),
        ("Replace Functionality", test_replace_functionality),
        ("Safety Mechanisms", test_safety_mechanisms),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func(repo_dir)
            test_results.append({
                "name": test_name,
                "success": result["success"],
                "error": result.get("error")
            })
        except Exception as e:
            test_results.append({
                "name": test_name,
                "success": False,
                "error": str(e)
            })
    
    # Print summary
    print("\n" + "="*50)
    print("TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    failed = 0
    
    for result in test_results:
        status = "PASS" if result["success"] else "FAIL"
        print(f"{status:4} | {result['name']}")
        if not result["success"] and result.get("error"):
            print(f"      Error: {result['error']}")
        
        if result["success"]:
            passed += 1
        else:
            failed += 1
    
    print("-"*50)
    print(f"Total: {passed + failed} | Passed: {passed} | Failed: {failed}")
    
    # Cleanup
    import shutil
    shutil.rmtree(repo_dir, ignore_errors=True)
    
    return failed == 0

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)