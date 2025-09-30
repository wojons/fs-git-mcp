import pytest
import tempfile
import os
import subprocess
from pathlib import Path
from mcp_server.git_backend.repo import RepoRef
from mcp_server.tools.reader import ReadIntent, extract_tool


@pytest.fixture
def temp_repo_with_file():
    """Create a temporary git repository with test file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize git repo
        subprocess.run(["git", "init", temp_dir], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        
        # Create test file with content
        test_file = Path(temp_dir) / "test.py"
        test_content = '''#!/usr/bin/env python3
def hello():
    """Say hello."""
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
        subprocess.run(["git", "-C", temp_dir, "add", "test.py"], check=True)
        subprocess.run(["git", "-C", temp_dir, "commit", "-m", "Add test file"], check=True)
        
        yield RepoRef(root=temp_dir), test_file


def test_extract_simple_query(temp_repo_with_file):
    """Test extracting spans with simple query."""
    repo, test_file = temp_repo_with_file
    
    intent = ReadIntent(
        path=str(test_file),
        query="Hello",
        before=1,
        after=1
    )
    
    result = extract_tool(repo, intent)
    
    assert result.spans is not None
    assert len(result.spans) == 1
    span = result.spans[0]
    assert span['start'] == 2
    assert span['end'] == 5
    assert len(span['lines']) == 3  # Fixed: should be 3 lines, not 4
    assert 'print("Hello, World!")' in span['lines'][1]


def test_extract_regex_query(temp_repo_with_file):
    """Test extracting spans with regex query."""
    repo, test_file = temp_repo_with_file
    
    intent = ReadIntent(
        path=str(test_file),
        query=r"def\s+\w+",
        regex=True,
        before=0,
        after=1
    )
    
    result = extract_tool(repo, intent)
    
    # Should find 4 function definitions (hello, add, __init__, increment)
    assert result.spans is not None
    assert len(result.spans) == 4  # Fixed: should be 4, not 3
    
    # Check first function
    assert 'def hello():' in result.spans[0]['lines'][0]
    assert '"""Say hello."""' in result.spans[0]['lines'][1]
    
    # Check second function
    assert 'def add(a, b):' in result.spans[1]['lines'][0]
    assert '"""Add two numbers."""' in result.spans[1]['lines'][1]
    
    # Check __init__ method
    assert 'def __init__(self):' in result.spans[2]['lines'][0]
    
    # Check increment method
    assert 'def increment(self):' in result.spans[3]['lines'][0]


def test_extract_max_spans_limit(temp_repo_with_file):
    """Test max_spans parameter."""
    repo, test_file = temp_repo_with_file
    
    intent = ReadIntent(
        path=str(test_file),
        query=r"def\s+\w+",
        regex=True,
        max_spans=2
    )
    
    result = extract_tool(repo, intent)
    
    # Should only return 2 spans due to limit
    assert result.spans is not None
    assert len(result.spans) == 2


def test_extract_history_included(temp_repo_with_file):
    """Test that history is included in result."""
    repo, test_file = temp_repo_with_file
    
    intent = ReadIntent(
        path=str(test_file),
        query="Hello"
    )
    
    result = extract_tool(repo, intent)
    
    # Should have history
    assert result.history is not None
    assert len(result.history) >= 1
    assert result.history[0]['subject'] == "Add test file"
    assert 'sha' in result.history[0]


def test_extract_content_included(temp_repo_with_file):
    """Test that content is included when requested."""
    repo, test_file = temp_repo_with_file
    
    intent = ReadIntent(
        path=str(test_file),
        query="Hello",
        include_content=True
    )
    
    result = extract_tool(repo, intent)
    
    # Should have full content
    assert result.content is not None
    assert 'def hello():' in result.content
    assert len(result.content) > 0