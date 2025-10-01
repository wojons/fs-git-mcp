import os
import pytest
from mcp_server.git_backend.safety import create_path_authorizer_from_config

def test_environment_variable_support():
    """Test that environment variables are used as fallback when CLI parameters are not provided."""
    
    # Save original environment
    orig_allowed = os.environ.get('FS_GIT_ALLOWED_PATHS')
    orig_denied = os.environ.get('FS_GIT_DENIED_PATHS')
    
    try:
        # Test with environment variables only
        os.environ['FS_GIT_ALLOWED_PATHS'] = 'src/**,docs/**/*.md'
        os.environ['FS_GIT_DENIED_PATHS'] = '!**/node_modules/**,!**/.git/**'
        
        # Create authorizer without CLI parameters
        authorizer = create_path_authorizer_from_config(repo_root='/tmp/test')
        
        # Should have patterns from environment variables
        assert authorizer.get_allowed_paths_summary() == 'Allowed patterns: src/**, docs/**/*.md'
        assert authorizer.get_denied_paths_summary() == 'Denied patterns: !**/node_modules/**, !**/.git/**'
        
        # Test path authorization works
        assert authorizer.is_path_allowed('src/main.py')
        assert authorizer.is_path_allowed('docs/readme.md')
        assert not authorizer.is_path_allowed('node_modules/package.json')
        assert not authorizer.is_path_allowed('.git/config')
        
    finally:
        # Restore original environment
        if orig_allowed is not None:
            os.environ['FS_GIT_ALLOWED_PATHS'] = orig_allowed
        else:
            os.environ.pop('FS_GIT_ALLOWED_PATHS', None)
        
        if orig_denied is not None:
            os.environ['FS_GIT_DENIED_PATHS'] = orig_denied
        else:
            os.environ.pop('FS_GIT_DENIED_PATHS', None)

def test_cli_parameters_override_environment():
    """Test that CLI parameters take precedence over environment variables."""
    
    # Save original environment
    orig_allowed = os.environ.get('FS_GIT_ALLOWED_PATHS')
    orig_denied = os.environ.get('FS_GIT_DENIED_PATHS')
    
    try:
        # Set environment variables
        os.environ['FS_GIT_ALLOWED_PATHS'] = 'env/**'
        os.environ['FS_GIT_DENIED_PATHS'] = '!env/denied/**'
        
        # Create authorizer with CLI parameters (should override env vars)
        authorizer = create_path_authorizer_from_config(
            repo_root='/tmp/test',
            allow_paths='cli/**',
            deny_paths='!cli/denied/**'
        )
        
        # Should have patterns from CLI parameters, not environment variables
        assert authorizer.get_allowed_paths_summary() == 'Allowed patterns: cli/**'
        assert authorizer.get_denied_paths_summary() == 'Denied patterns: !cli/denied/**'
        
        # Test path authorization works with CLI patterns
        assert authorizer.is_path_allowed('cli/file.py')
        assert not authorizer.is_path_allowed('env/file.py')  # Not in CLI allowed patterns
        
    finally:
        # Restore original environment
        if orig_allowed is not None:
            os.environ['FS_GIT_ALLOWED_PATHS'] = orig_allowed
        else:
            os.environ.pop('FS_GIT_ALLOWED_PATHS', None)
        
        if orig_denied is not None:
            os.environ['FS_GIT_DENIED_PATHS'] = orig_denied
        else:
            os.environ.pop('FS_GIT_DENIED_PATHS', None)

def test_no_patterns_no_environment():
    """Test that no patterns and no environment variables allows all paths."""
    
    # Ensure no environment variables are set
    orig_allowed = os.environ.get('FS_GIT_ALLOWED_PATHS')
    orig_denied = os.environ.get('FS_GIT_DENIED_PATHS')
    
    try:
        os.environ.pop('FS_GIT_ALLOWED_PATHS', None)
        os.environ.pop('FS_GIT_DENIED_PATHS', None)
        
        # Create authorizer without CLI parameters
        authorizer = create_path_authorizer_from_config(repo_root='/tmp/test')
        
        # Should allow all paths
        assert authorizer.get_allowed_paths_summary() == 'All paths allowed (except denied patterns)'
        assert authorizer.get_denied_paths_summary() == 'No denied patterns'
        assert authorizer.is_path_allowed('any/path/file.txt')
        
    finally:
        # Restore original environment
        if orig_allowed is not None:
            os.environ['FS_GIT_ALLOWED_PATHS'] = orig_allowed
        if orig_denied is not None:
            os.environ['FS_GIT_DENIED_PATHS'] = orig_denied