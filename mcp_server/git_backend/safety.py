import os
import re
import subprocess
from typing import List, Optional, Pattern
from pathlib import Path
from mcp_server.git_backend.repo import RepoRef

def glob_to_regex(glob_pattern: str) -> str:
    """
    Convert glob pattern to regex pattern.
    Supports ** (recursive), * (non-recursive), ? , and basic escaping.
    """
    i = 0
    parts = []
    n = len(glob_pattern)
    while i < n:
        c = glob_pattern[i]
        if c == '\\':
            # Escape next char
            i += 1
            if i < n:
                parts.append(re.escape(glob_pattern[i]))
            else:
                parts.append(re.escape(c))
        elif c == '*':
            if i + 1 < n and glob_pattern[i + 1] == '*':
                # ** matches any path segment including /
                parts.append('.*')
                i += 2
            else:
                # * matches within segment, no /
                parts.append('[^/]*')
                i += 1
        elif c == '?':
            parts.append('.')
            i += 1
        elif c == '[':
            # Handle character class
            j = i
            while j < n and glob_pattern[j] != ']':
                j += 1
            if j < n:
                class_str = glob_pattern[i:j+1]
                # Escape special in class
                escaped = ''.join(re.escape(ch) if ch in '^-[\\]' else ch for ch in class_str)
                parts.append(escaped)
                i = j + 1
            else:
                parts.append(re.escape(c))
                i += 1
        elif c in '.^$+?()|{}':
            parts.append(re.escape(c))
            i += 1
        else:
            parts.append(re.escape(c))
            i += 1
    regex = '^' + ''.join(parts) + '$'
    return regex

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
    
    Supports glob patterns (converted to regex), regex patterns, 
    and deny path syntax with ! prefix.
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
        self.allowed_regexes: List[Pattern[str]] = []
        self.denied_regexes: List[Pattern[str]] = []
        self.allowed_patterns = allowed_patterns or []
        self.denied_patterns = denied_patterns or []
        
        # Process allowed patterns
        for pattern in allowed_patterns or []:
            if pattern.startswith('r"') or pattern.startswith("r'") or '\\' in pattern:
                if pattern.startswith('r"') or pattern.startswith("r'"):
                    raw_pattern = pattern[2:-1] if pattern.endswith(('"', "'")) else pattern[1:]
                else:
                    raw_pattern = pattern
                self.allowed_regexes.append(re.compile(raw_pattern))
            else:
                # Convert glob to regex
                glob_regex = glob_to_regex(pattern)
                self.allowed_regexes.append(re.compile(glob_regex))
        
        # Process denied patterns
        for pattern in denied_patterns or []:
            clean_pattern = pattern.lstrip('!')
            if clean_pattern.startswith('r"') or clean_pattern.startswith("r'") or '\\' in clean_pattern:
                if clean_pattern.startswith('r"') or clean_pattern.startswith("r'"):
                    raw_pattern = clean_pattern[2:-1] if clean_pattern.endswith(('"', "'")) else clean_pattern[1:]
                else:
                    raw_pattern = clean_pattern
                self.denied_regexes.append(re.compile(raw_pattern))
            else:
                # Convert glob to regex
                glob_regex = glob_to_regex(clean_pattern)
                self.denied_regexes.append(re.compile(glob_regex))
    
    def _matches_regex(self, rel_path: str, regex_patterns: List[Pattern[str]]) -> bool:
        """
        Check if rel_path matches any regex pattern.
        """
        for pattern in regex_patterns:
            if pattern.fullmatch(rel_path):
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
        if self._matches_regex(rel_path, self.denied_regexes):
            return False
        
        # If no allowed patterns specified, allow everything (except denied)
        if not self.allowed_regexes:
            return True
        
        # Check allowed patterns
        return self._matches_regex(rel_path, self.allowed_regexes)
    
    def get_allowed_paths_summary(self) -> str:
        """Get a summary of allowed path patterns."""
        if not self.allowed_patterns:
            return "All paths allowed (except denied patterns)"
        
        return f"Allowed patterns: {', '.join(self.allowed_patterns)}"
    
    def get_denied_paths_summary(self) -> str:
        """Get a summary of denied path patterns."""
        if not self.denied_patterns:
            return "No denied patterns"
        
        return f"Denied patterns: {', '.join(self.denied_patterns)}"


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