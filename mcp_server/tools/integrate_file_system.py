from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.safety import enforce_path_under_root


def read_file(repo: RepoRef, path: str) -> str:
    """
    Read file content.
    """
    abs_path = enforce_path_under_root(repo, path)
    with open(abs_path, 'r') as f:
        return f.read()


def stat_file(repo: RepoRef, path: str) -> dict:
    """
    Get file stats.
    """
    abs_path = enforce_path_under_root(repo, path)
    import os
    stat = os.stat(abs_path)
    return {
        'size': stat.st_size,
        'mtime': stat.st_mtime,
        'is_file': os.path.isfile(abs_path),
        'is_dir': os.path.isdir(abs_path)
    }


def list_dir(repo: RepoRef, path: str, recursive: bool = False) -> list[str]:
    """
    List directory contents.
    """
    abs_path = enforce_path_under_root(repo, path)
    if recursive:
        import os
        return [os.path.join(root, file) for root, dirs, files in os.walk(abs_path) for file in files]
    else:
        import os
        return os.listdir(abs_path)


def make_dir(repo: RepoRef, path: str, recursive: bool = False) -> dict:
    """
    Create directory.
    """
    abs_path = enforce_path_under_root(repo, path)
    import os
    os.makedirs(abs_path, exist_ok=True)
    return {'ok': True}