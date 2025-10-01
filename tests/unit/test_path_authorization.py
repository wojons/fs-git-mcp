#!/usr/bin/env python3
"""
Tests for path authorization functionality.
"""

import pytest
import tempfile
import os
from pathlib import Path

from mcp_server.git_backend.safety import (
    PathAuthorizer,
    create_path_authorizer_from_config,
    enforce_path_authorization
)


class TestPathAuthorizer:
    """Test cases for PathAuthorizer class."""
    
    def test_allow_all_patterns(self):
        """Test that when no patterns are specified, all paths are allowed."""
        authorizer = PathAuthorizer()
        
        assert authorizer.is_path_allowed("/any/path") is True
        assert authorizer.is_path_allowed("/repo/src/main.py") is True
        assert authorizer.is_path_allowed("relative/path") is True
    
    def test_allowed_glob_patterns(self):
        """Test allowed glob patterns."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**", "docs/**/*.md", "*.txt"],
            repo_root="/test/repo"
        )
        
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/src/components/button.js") is True
        assert authorizer.is_path_allowed("/test/repo/docs/readme.md") is True
        assert authorizer.is_path_allowed("/test/repo/config.txt") is True
        
        # Denied paths
        assert authorizer.is_path_allowed("/test/repo/tests/test.py") is False
        assert authorizer.is_path_allowed("/test/repo/.env") is False
    
    def test_denied_glob_patterns(self):
        """Test denied glob patterns."""
        authorizer = PathAuthorizer(
            denied_patterns=["!**/node_modules/**", "!**/.git/**", "!*.secret"],
            repo_root="/test/repo"
        )
        
        # Should be allowed (not in denied patterns)
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/docs/readme.md") is True
        
        # Should be denied
        assert authorizer.is_path_allowed("/test/repo/node_modules/react/index.js") is False
        assert authorizer.is_path_allowed("/test/repo/.git/config") is False
        assert authorizer.is_path_allowed("/test/repo/config.secret") is False
    
    def test_combined_allow_and_deny_patterns(self):
        """Test combined allowed and denied patterns."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**", "docs/**"],
            denied_patterns=["!**/test/**", "!**/*.tmp"],
            repo_root="/test/repo"
        )
        
        # Allowed and not denied
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/docs/readme.md") is True
        
        # Denied takes precedence even if in allowed
        assert authorizer.is_path_allowed("/test/repo/src/test/test.py") is False
        assert authorizer.is_path_allowed("/test/repo/src/main.tmp") is False
        
        # Not in allowed patterns
        assert authorizer.is_path_allowed("/test/repo/build/output.js") is False
    
    def test_regex_patterns(self):
        """Test regex patterns."""
        authorizer = PathAuthorizer(
            allowed_patterns=[r".*\.py$", r".*\.js$"],
            denied_patterns=[r".*test\.py$", r".*\.secret$"],
            repo_root="/test/repo"
        )
        
        # Allowed regex patterns
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/components/app.js") is True
        
        # Denied regex takes precedence
        assert authorizer.is_path_allowed("/test/repo/src/test.py") is False
        assert authorizer.is_path_allowed("/test/repo/config.secret") is False
        
        # Not matching allowed patterns
        assert authorizer.is_path_allowed("/test/repo/docs/readme.md") is False
    
    def test_relative_paths(self):
        """Test relative path handling."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**", "*.md"],
            repo_root="/test/repo"
        )
        
        # Relative paths should work
        assert authorizer.is_path_allowed("src/main.py") is True
        assert authorizer.is_path_allowed("readme.md") is True
        assert authorizer.is_path_allowed("test.py") is False
    
    def test_summary_methods(self):
        """Test summary methods."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**", "docs/**"],
            denied_patterns=["!**/test/**"]
        )
        
        allowed_summary = authorizer.get_allowed_paths_summary()
        denied_summary = authorizer.get_denied_paths_summary()
        
        assert "src/**" in allowed_summary
        assert "docs/**" in allowed_summary
        assert "**/test/**" in denied_summary
    
    def test_empty_repo_root(self):
        """Test behavior when repo_root is not specified."""
        authorizer = PathAuthorizer(allowed_patterns=["*.py"])
        
        # Should still work with absolute paths
        assert authorizer.is_path_allowed("/any/path/file.py") is True
        assert authorizer.is_path_allowed("/any/path/file.js") is False


class TestPathAuthorizerConfig:
    """Test path authorizer creation from configuration."""
    
    def test_create_from_config_allow_only(self):
        """Test creating authorizer from config with only allowed patterns."""
        authorizer = create_path_authorizer_from_config(
            repo_root="/test/repo",
            allow_paths="src/**,docs/**/*.md",
            deny_paths=None
        )
        
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/docs/readme.md") is True
        assert authorizer.is_path_allowed("/test/repo/test.py") is False
    
    def test_create_from_config_deny_only(self):
        """Test creating authorizer from config with only denied patterns."""
        authorizer = create_path_authorizer_from_config(
            repo_root="/test/repo",
            allow_paths=None,
            deny_paths="!**/node_modules/**,!**/.git/**"
        )
        
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/node_modules/react/index.js") is False
        assert authorizer.is_path_allowed("/test/repo/.git/config") is False
    
    def test_create_from_config_both(self):
        """Test creating authorizer from config with both allowed and denied patterns."""
        authorizer = create_path_authorizer_from_config(
            repo_root="/test/repo",
            allow_paths="src/**,docs/**",
            deny_paths="!**/test/**"
        )
        
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/src/test/main.py") is False
        assert authorizer.is_path_allowed("/test/repo/docs/readme.md") is True
        assert authorizer.is_path_allowed("/test/repo/build/output.js") is False
    
    def test_create_from_config_empty(self):
        """Test creating authorizer from config with no patterns."""
        authorizer = create_path_authorizer_from_config()
        
        assert authorizer.is_path_allowed("/any/path") is True
    
    def test_config_whitespace_handling(self):
        """Test that whitespace in config strings is handled properly."""
        authorizer = create_path_authorizer_from_config(
            repo_root="/test/repo",
            allow_paths=" src/** , docs/** ",
            deny_paths=" !**/test/** , !**/tmp/** "
        )
        
        assert authorizer.is_path_allowed("/test/repo/src/main.py") is True
        assert authorizer.is_path_allowed("/test/repo/src/test/main.py") is False


class TestEnforcePathAuthorization:
    """Test the enforce_path_authorization function."""
    
    def test_allowed_path(self):
        """Test that allowed paths are returned as absolute paths."""
        authorizer = PathAuthorizer(allowed_patterns=["src/**"])
        
        result = enforce_path_authorization("src/main.py", authorizer)
        assert os.path.isabs(result)
        assert result.endswith("src/main.py")
    
    def test_denied_path_raises_error(self):
        """Test that denied paths raise ValueError."""
        authorizer = PathAuthorizer(allowed_patterns=["src/**"])
        
        with pytest.raises(ValueError) as exc_info:
            enforce_path_authorization("docs/readme.md", authorizer)
        
        assert "not authorized" in str(exc_info.value)
        assert "docs/readme.md" in str(exc_info.value)
    
    def test_no_patterns_allows_all(self):
        """Test that authorizer with no patterns allows all paths."""
        authorizer = PathAuthorizer()
        
        result = enforce_path_authorization("any/path/file.txt", authorizer)
        assert os.path.isabs(result)


if __name__ == "__main__":
    pytest.main([__file__])