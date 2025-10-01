import subprocess
from mcp_server.git_backend.repo import RepoRef
from typing import Dict, Any, List

def get_file_history(repo: RepoRef, path: str, limit: int = 10) -> List[Dict[str, str]]:
    try:
        result = subprocess.run(
            ["git", "-C", repo.root, "log", f"--oneline", f"-{limit}", "--", path],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')
        history = []
        for line in lines:
            if line:
                parts = line.split(' ', 1)
                sha = parts[0]
                subject = parts[1] if len(parts) > 1 else ""
                history.append({"sha": sha, "subject": subject})
        return history
    except subprocess.CalledProcessError:
        return []

def read_with_history(repo: RepoRef, path: str, history_limit: int = 10) -> Dict[str, Any]:
    """
    Read file content and git history.
    """
    from mcp_server.git_backend.safety import enforce_path_under_root
    
    # Read content
    try:
        abs_path = enforce_path_under_root(repo, path)
        with open(abs_path, 'r') as f:
            content = f.read()
    except (FileNotFoundError, ValueError):
        content = None
    
    # Get history
    history = get_file_history(repo, path, history_limit)
    
    return {'path': path, 'content': content, 'history': history}