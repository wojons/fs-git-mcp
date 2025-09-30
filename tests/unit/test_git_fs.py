import pytest
import tempfile
import os
import subprocess
from pathlib import Path
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.templates import CommitTemplate, load_default_template
from mcp_server.tools.git_fs import WriteRequest, write_and_commit_tool


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize git repo
        subprocess.run(["git", "init", temp_dir], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        
        # Create initial commit
        init_file = Path(temp_dir) / "README.md"
        init_file.write_text("# Test Repository\n")
        subprocess.run(["git", "-C", temp_dir, "add", "README.md"], check=True)
        subprocess.run(["git", "-C", temp_dir, "commit", "-m", "Initial commit"], check=True)
        
        yield RepoRef(root=temp_dir)


def test_write_and_commit_new_file(temp_repo):
    """Test writing and committing a new file."""
    template = CommitTemplate(subject="[{op}] {path} – {summary}")
    request = WriteRequest(
        repo=temp_repo,
        path="test.txt",
        content="Hello, World!",
        template=template
    )
    
    result = write_and_commit_tool(request)
    
    # Verify file was created
    file_path = Path(temp_repo.root) / "test.txt"
    assert file_path.exists()
    assert file_path.read_text() == "Hello, World!"
    
    # Verify commit was created
    assert result.commit_sha is not None
    assert result.path == "test.txt"
    assert result.branch == temp_repo.get_current_branch()
    
    # Verify git history
    result = subprocess.run(
        ["git", "-C", temp_repo.root, "log", "--oneline", "-1"],
        capture_output=True, text=True, check=True
    )
    assert "[write] test.txt – file write" in result.stdout


def test_write_and_commit_existing_file(temp_repo):
    """Test writing and committing an existing file."""
    # Create initial file
    test_file = Path(temp_repo.root) / "existing.txt"
    test_file.write_text("Initial content")
    subprocess.run(["git", "-C", temp_repo.root, "add", "existing.txt"], check=True)
    subprocess.run(["git", "-C", temp_repo.root, "commit", "-m", "Add existing file"], check=True)
    
    template = CommitTemplate(subject="[{op}] {path} – {summary}")
    request = WriteRequest(
        repo=temp_repo,
        path="existing.txt",
        content="Updated content",
        template=template
    )
    
    result = write_and_commit_tool(request)
    
    # Verify file was updated
    assert test_file.exists()
    assert test_file.read_text() == "Updated content"
    
    # Verify commit was created
    assert result.commit_sha is not None
    assert result.path == "existing.txt"


def test_write_and_commit_uniqueness_check(temp_repo):
    """Test commit message uniqueness check."""
    template = CommitTemplate(subject="[{op}] {path} – {summary}")
    
    # First commit
    request1 = WriteRequest(
        repo=temp_repo,
        path="test1.txt",
        content="Content 1",
        template=template
    )
    result1 = write_and_commit_tool(request1)
    
    # Second commit with same message template (should get auto-suffixed)
    request2 = WriteRequest(
        repo=temp_repo,
        path="test2.txt", 
        content="Content 2",
        template=template
    )
    result2 = write_and_commit_tool(request2)
    
    # Verify both commits exist
    result = subprocess.run(
        ["git", "-C", temp_repo.root, "log", "--oneline"],
        capture_output=True, text=True, check=True
    )
    lines = result.stdout.strip().split('\n')
    assert len(lines) >= 3  # Initial + 2 test commits
    
    # Verify the messages are different
    commit_messages = [line.split(' ', 1)[1] for line in lines if 'test' in line]
    assert len(commit_messages) == 2
    assert commit_messages[0] != commit_messages[1]


def test_write_and_commit_invalid_path(temp_repo):
    """Test that paths outside repo root are rejected."""
    template = CommitTemplate(subject="[{op}] {path} – {summary}")
    request = WriteRequest(
        repo=temp_repo,
        path="../outside.txt",
        content="Should fail",
        template=template
    )
    
    with pytest.raises(ValueError, match="outside repo root"):
        write_and_commit_tool(request)