from pydantic import BaseModel
import re
from typing import List, Dict, Any, Optional
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.history import get_file_history
from mcp_server.git_backend.safety import enforce_path_under_root


class ReadIntent(BaseModel):
    path: str
    query: Optional[str] = None
    regex: bool = False
    before: int = 3
    after: int = 3
    max_spans: int = 20
    include_content: bool = False
    history_limit: int = 10


class ReadResult(BaseModel):
    path: str
    spans: Optional[List[Dict[str, Any]]] = None
    history: List[Dict[str, str]]
    content: Optional[str] = None


def extract_tool(repo: RepoRef, intent: ReadIntent) -> ReadResult:
    """
    Extract spans from file based on query.
    """
    abs_path = enforce_path_under_root(repo, intent.path)
    with open(abs_path, 'r') as f:
        lines = f.readlines()
    
    spans = []
    if intent.query:
        if intent.regex:
            pattern = re.compile(intent.query)
            for i, line in enumerate(lines):
                if pattern.search(line):
                    start = max(0, i - intent.before)
                    end = min(len(lines), i + intent.after + 1)
                    span_lines = lines[start:end]
                    spans.append({
                        'start': start,
                        'end': end,
                        'lines': [l.rstrip() for l in span_lines]
                    })
                    if len(spans) >= intent.max_spans:
                        break
        else:
            for i, line in enumerate(lines):
                if intent.query in line:
                    start = max(0, i - intent.before)
                    end = min(len(lines), i + intent.after + 1)
                    span_lines = lines[start:end]
                    spans.append({
                        'start': start,
                        'end': end,
                        'lines': [l.rstrip() for l in span_lines]
                    })
                    if len(spans) >= intent.max_spans:
                        break
    
    history = get_file_history(repo, intent.path, intent.history_limit)
    
    content = ''.join(lines) if intent.include_content else None
    
    return ReadResult(
        path=intent.path,
        spans=spans,
        history=history,
        content=content
    )


def answer_about_file_tool(repo: RepoRef, path: str, question: str, before: int = 3, after: int = 3, max_spans: int = 20) -> Dict[str, Any]:
    """
    Answer questions about file content.
    """
    # Placeholder for AI-based answering
    return {"answer": "Placeholder answer", "citations": []}