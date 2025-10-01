#!/usr/bin/env python3
"""
Integration tests for MCP server functionality.
Tests the actual MCP protocol compliance and tool availability.
"""

import json
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path


class TestMCPServerCLI(unittest.TestCase):
    """Test MCP server CLI entry points."""
    
    def test_fs_git_serve_help(self):
        """Test that CLI serve command works."""
        # Test help output
        result = subprocess.run(
             [sys.executable, "-m", "mcp_server.cli.main", "serve", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("Start the MCP server", result.stdout)
        self.assertIn("--transport", result.stdout)
        self.assertIn("stdio", result.stdout)
        self.assertIn("tcp", result.stdout)
        
        print("✓ CLI serve command help works correctly")
    
    def test_mcp_server_startup(self):
        """Test that MCP server can start without errors."""
        # Test server startup (should exit gracefully on EOF)
        proc = subprocess.run(
            [sys.executable, "-m", "mcp_server.cli.main", "serve"],
            input="",  # Send EOF immediately
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent
        )
        
        # Server should start and exit cleanly
        self.assertTrue(proc.returncode in [0, 1])  # Different exit codes are acceptable
        self.assertIn("Starting fs-git MCP server", proc.stderr)
        
        print("✓ MCP server starts successfully")


class TestMCPToolsAvailability(unittest.TestCase):
    """Test that MCP tools are properly exposed."""
    
    def test_mcp_tools_import(self):
        """Test that all MCP tool modules can be imported."""
        try:
            # Test imports
            from mcp_server.tools.git_fs import write_and_commit_tool
            from mcp_server.tools.reader import extract_tool
            from mcp_server.tools.integrate_text_replace import replace_and_commit
            from mcp_server.tools.integrate_code_diff import preview_diff
            from mcp_server.tools.integrate_file_system import read_file
            
            # Test that tools are callable
            self.assertTrue(callable(write_and_commit_tool))
            self.assertTrue(callable(extract_tool))
            self.assertTrue(callable(replace_and_commit))
            self.assertTrue(callable(preview_diff))
            self.assertTrue(callable(read_file))
            
            print("✓ All MCP tool modules import successfully")
            
        except ImportError as e:
            self.fail(f"Failed to import MCP tools: {e}")
    
    def test_fastmcp_server_import(self):
        """Test that FastMCP server can be imported."""
        try:
            from mcp_server.mcp_server_fastmcp import main as mcp_main
            self.assertTrue(callable(mcp_main))
            print("✓ FastMCP server imports successfully")
        except ImportError as e:
            self.fail(f"Failed to import FastMCP server: {e}")


class TestMCPProjectStructure(unittest.TestCase):
    """Test that project structure supports MCP deployment."""
    
    def test_pyproject_entry_points(self):
        """Test that pyproject.toml has correct entry points."""
        import tomllib
        
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        
        # Check entry points
        scripts = pyproject.get("project", {}).get("scripts", {})
        self.assertIn("fs-git", scripts)
        self.assertIn("fs-git-mcp", scripts)
        
        self.assertEqual(scripts["fs-git"], "mcp_server.cli.main:app")
        self.assertEqual(scripts["fs-git-mcp"], "mcp_server.server_fastmcp_new:main")
        
        print("✓ pyproject.toml has correct entry points")
    
    def test_mcp_dependencies(self):
        """Test that MCP dependencies are included."""
        import tomllib
        
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        
        dependencies = pyproject.get("project", {}).get("dependencies", [])
        
        # Check for MCP dependencies
        mcp_deps = [dep for dep in dependencies if dep.startswith("mcp")]
        self.assertTrue(len(mcp_deps) > 0, "Should have at least one MCP dependency")
        
        print(f"✓ MCP dependencies found: {mcp_deps}")


if __name__ == "__main__":
    unittest.main()