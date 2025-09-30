import subprocess
from .repo import RepoRef

def get_file_history(repo: RepoRef, path: str, limit: int = 10) -> list:
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