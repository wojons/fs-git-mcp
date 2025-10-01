import os
import re
import subprocess
import fnmatch
from pathlib import Path
from typing import List, Optional, Pattern, Set
from mcp_server.git_backend.repo import RepoRef

def enforce_path_under_root(repo: RepoRef, path: str) -> str:
    abs_path = os.path.abspath(os.path.join(repo.root, path))
    if not abs_path.startswith(repo.root):
        raise ValueError(f"Path {path} is outside repo root {repo.root}")
    return abs_path

def enforce_repo_root(repo_root: str, file_path: str) -> bool:
    """
    Ensure file_path is within repo_root to prevent path traversal.
    """
    try:
        resolved_root = Path(repo_root).resolve()
        resolved_path = Path(file_path).resolve()
        return resolved_path.is_relative_to(resolved_root)
    except (OSError, ValueError):
        return False

def set_git_safe_directory(repo_root: str) -> None:
    """
    Set git safe.directory for the repo root.
    """
    os.environ['GIT_CONFIG_PARAMETERS'] = f"safe.directory={repo_root}"

def check_dirty_tree(repo: RepoRef) -> bool:
    try:
        result = subprocess.run(["git", "-C", repo.root, "status", "--porcelain"], capture_output=True, text=True, check=True)
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return True  # Assume dirty if check fails

def validate_commit_message(subject: str, body: Optional[str] = None) -> tuple[bool, list[str]]:
    """
    Validate commit message: subject <=72 chars, required tokens.
    """
    errors = []
    if len(subject) > 72:
        errors.append("Subject exceeds 72 characters")
    if '{op}' not in subject or '{path}' not in subject or '{summary}' not in subject:
        errors.append("Subject must include {op}, {path}, {summary} tokens")
    return len(errors) == 0, errors


class PathAuthorizer:
    """
    Path authorization system for controlling access to files and directories.
    
    Supports glob patterns, regex patterns, and deny path syntax with ! prefix.
    """
    
    def __init__(self, 
                 allowed_patterns: Optional[List[str]] = None,
                 denied_patterns: Optional[List[str]] = None,
                 repo_root: Optional[str] = None):
        """
        Initialize path authorizer.
        
        Args:
            allowed_patterns: List of glob/regex patterns for allowed paths
            denied_patterns: List of glob/regex patterns for denied paths (with ! prefix)
            repo_root: Repository root path for resolving relative paths
        """
        self.repo_root = repo_root
        self.allowed_patterns: List[Pattern[str]] = []
        self.denied_patterns: List[Pattern[str]] = []
        self.denied_glob_patterns: List[str] = []
        self.allowed_glob_patterns: List[str] = []
        
        # Process allowed patterns
        if allowed_patterns:
            for pattern in allowed_patterns:
                if self._is_regex_pattern(pattern):
                    self.allowed_patterns.append(re.compile(pattern))
                else:
                    self.allowed_glob_patterns.append(pattern)
        
        # Process denied patterns
        if denied_patterns:
            for pattern in denied_patterns:
                # Remove ! prefix if present
                clean_pattern = pattern[1:] if pattern.startswith('!') else pattern
                if self._is_regex_pattern(clean_pattern):
                    self.denied_patterns.append(re.compile(clean_pattern))
                else:
                    self.denied_glob_patterns.append(clean_pattern)
    
    def _is_regex_pattern(self, pattern: str) -> bool:
        """
        Determine if a pattern is a regex pattern.
        """
        # Raw string patterns (starting with r") are likely regex
        if pattern.startswith('r"') or pattern.startswith("r'"):
            return True
        
        # Common glob patterns - treat these as glob, not regex
        if '**' in pattern or pattern.endswith('*') or '?' in pattern:
            return False
        
        # Patterns with regex-specific syntax
        regex_indicators = ['(', ')', '{', '}', '^', '$', '+']
        return any(indicator in pattern for indicator in regex_indicators)
    
    def _matches_glob(self, path: str, glob_patterns: List[str]) -> bool:
        """
        Check if path matches any of the glob patterns.
        
        Uses custom recursive glob matching with ** support.
        Assumes path is the relative path string.
        """
        path_parts = [part for part in path.split('/') if part]
        
        for pattern_str in glob_patterns:
            pattern = pattern_str.replace(os.sep, '/')
            pattern_parts = [part for part in pattern.split('/') if part]
            if self._matches_pattern_parts(path_parts, pattern_parts):
                return True
        
        return False
    
    def _matches_pattern_parts(self, path_parts: List[str], pattern_parts: List[str]) -> bool:
        """
        Check if path_parts match pattern_parts using recursive glob matching.
        """
        if not pattern_parts:
            return len(path_parts) == 0
        
        # Special case for single-part non-** patterns: match against basename
        if len(pattern_parts) == 1 and pattern_parts[0] != '**':
            if not path_parts:
                return False
            return fnmatch.fnmatch(path_parts[-1], pattern_parts[0])
        
        # Full recursive matching for multi-part or ** patterns
        def _match(i: int, j: int) -> bool:
            if j == len(pattern_parts):
                return i == len(path_parts)
            
            if i == len(path_parts):
                # Remaining patterns must all be **
                return all(p == '**' for p in pattern_parts[j:])
            
            pat = pattern_parts[j]
            
            if pat == '**':
                # Match zero directories
                if _match(i, j + 1):
                    return True
                # Match one or more directories (stay at j, advance i)
                return _match(i + 1, j)
            else:
                # Match current segment
                if fnmatch.fnmatch(path_parts[i], pat):
                    return _match(i + 1, j + 1)
                return False
        
        return _match(0, 0)
    
    def _matches_regex(self, path: str, regex_patterns: List[Pattern[str]]) -> bool:
        """
        Check if path matches any of the regex patterns.
        """
        for pattern in regex_patterns:
            if pattern.search(path):
                return True
        return False
    
    def is_path_allowed(self, path: str) -> bool:
        """
        Check if a path is allowed based on the configured patterns.
        Args:
            path: File path to check (absolute or relative to repo_root)
            
        Returns:
            True if path is allowed, False otherwise
        """
        # Calculate absolute path
        if self.repo_root and not os.path.isabs(path):
            abs_path = os.path.abspath(os.path.join(self.repo_root, path))
        else:
            abs_path = os.path.abspath(path) if os.path.isabs(path) else path
        
        # Calculate relative path for consistent matching
        if self.repo_root:
            try:
                rel_path = os.path.relpath(abs_path, self.repo_root).replace(os.sep, '/')
                if rel_path.startswith('..'):
                    return False
            except ValueError:
                return False
        else:
            rel_path = path.replace(os.sep, '/').lstrip('/')
        
        # Check denied patterns first (deny takes precedence)
        if self.denied_patterns or self.denied_glob_patterns:
            if self._matches_regex(rel_path, self.denied_patterns):
                return False
            if self._matches_glob(rel_path, self.denied_glob_patterns):
                return False
        
        # If no allowed patterns specified, allow everything (except denied)
        if not self.allowed_patterns and not self.allowed_glob_patterns:
            return True
        
        # Check allowed patterns
        if self.allowed_patterns or self.allowed_glob_patterns:
            if self._matches_regex(rel_path, self.allowed_patterns):
                return True
            if self._matches_glob(rel_path, self.allowed_glob_patterns):
                return True
            return False  # Not in allowed patterns
        
        return True
    
    def get_allowed_paths_summary(self) -> str:
        """Get a summary of allowed path patterns."""
        if not self.allowed_patterns and not self.allowed_glob_patterns:
            return "All paths allowed (except denied patterns)"
        
        patterns = []
        patterns.extend([p.pattern for p in self.allowed_patterns])
        patterns.extend(self.allowed_glob_patterns)
        return f"Allowed patterns: {', '.join(patterns)}"
    
    def get_denied_paths_summary(self) -> str:
        """Get a summary of denied path patterns."""
        if not self.denied_patterns and not self.denied_glob_patterns:
            return "No denied patterns"
        
        patterns = []
        patterns.extend([p.pattern for p in self.denied_patterns])
        patterns.extend([f"!{p}" for p in self.denied_glob_patterns])
        return f"Denied patterns: {', '.join(patterns)}"


def create_path_authorizer_from_config(repo_root: Optional[str] = None,
                                     allow_paths: Optional[str] = None,
                                     deny_paths: Optional[str] = None) -> PathAuthorizer:
    """
    Create a PathAuthorizer from configuration strings.
    
    Args:
        repo_root: Repository root path
        allow_paths: Comma-separated string of allowed path patterns
        deny_paths: Comma-separated string of denied path patterns
        
    Returns:
        Configured PathAuthorizer instance
    """
    import os
    
    allowed_list = None
    denied_list = None
    
    # Use CLI parameters if provided, otherwise check environment variables
    if allow_paths:
        allowed_list = [p.strip() for p in allow_paths.split(',') if p.strip()]
    else:
        # Fallback to environment variable
        env_allowed = os.environ.get('FS_GIT_ALLOWED_PATHS')
        if env_allowed:
            allowed_list = [p.strip() for p in env_allowed.split(',') if p.strip()]
    
    if deny_paths:
        denied_list = [p.strip() for p in deny_paths.split(',') if p.strip()]
    else:
        # Fallback to environment variable
        env_denied = os.environ.get('FS_GIT_DENIED_PATHS')
        if env_denied:
            denied_list = [p.strip() for p in env_denied.split(',') if p.strip()]
    
    return PathAuthorizer(
        allowed_patterns=allowed_list,
        denied_patterns=denied_list,
        repo_root=repo_root
    )


def enforce_path_authorization(path: str, authorizer: PathAuthorizer) -> str:
    """
    Enforce path authorization and return the absolute path if allowed.
    
    Args:
        path: Path to check
        authorizer: PathAuthorizer instance
        
    Returns:
        Absolute path if authorized
        
    Raises:
        ValueError: If path is not authorized
    """
    if not authorizer.is_path_allowed(path):
        denied_summary = authorizer.get_denied_paths_summary()
        allowed_summary = authorizer.get_allowed_paths_summary()
        raise ValueError(
            f"Path '{path}' is not authorized. "
            f"{denied_summary}. {allowed_summary}"
        )
    
    return os.path.abspath(path)