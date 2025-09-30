import typer
from pathlib import Path
from typing import Optional
from ..git_backend.repo import RepoRef
from ..git_backend.templates import load_default_template, CommitTemplate
from ..tools.git_fs import write_and_commit_tool, read_with_history_tool, start_staged_tool, staged_write_tool, staged_preview_tool, finalize_tool, abort_tool, WriteRequest, FinalizeOptions
from ..tools.reader import extract_tool, answer_about_file_tool, ReadIntent

app = typer.Typer()


@app.command()
def write(repo: str, path: str, file: str = None, subject: str = None, reason: str = None, ticket: str = None, op: str = "edit"):
    """
    Write and commit a file.
    """
    repo_ref = RepoRef(root=repo)
    template = load_default_template()
    if file:
        with open(file, 'r') as f:
            content = f.read()
    else:
        content = typer.prompt("Content")
    variables = {'op': str(op), 'path': str(path), 'summary': 'CLI write', 'reason': str(reason or ''), 'ticket': str(ticket or ''), 'files': '', 'refs': ''}
    result = write_and_commit_tool(WriteRequest(repo=repo_ref, path=path, content=content, template=template))
    typer.echo(f"Committed {result.commit_sha} on {result.branch}")


@app.command()
def staged_start(repo: str, ticket: str = None):
    """
    Start a staged session.
    """
    repo_ref = RepoRef(root=repo)
    session = start_staged_tool(repo_ref, ticket)
    typer.echo(f"Started session {session.id}")


@app.command()
def staged_write(session_id: str, repo: str, path: str, file: str = None, summary: str = "staged write"):
    """
    Write in staged session.
    """
    repo_ref = RepoRef(root=repo)
    template = load_default_template()
    if file:
        with open(file, 'r') as f:
            content = f.read()
    else:
        content = typer.prompt("Content")
    variables = {'op': 'staged', 'path': path, 'summary': summary}
    result = staged_write_tool(session_id, WriteRequest(repo=repo_ref, path=path, content=content, template=template))
    typer.echo(f"Staged write {result.commit_sha}")


@app.command()
def staged_preview(session_id: str):
    """
    Preview staged changes.
    """
    preview = staged_preview_tool(session_id)
    typer.echo(preview.diff)


@app.command()
def staged_finalize(session_id: str, strategy: str = "merge-ff"):
    """
    Finalize staged session.
    """
    options = FinalizeOptions(strategy=strategy)
    result = finalize_tool(session_id, options)
    typer.echo(f"Finalized {result['merged_sha']}")


@app.command()
def staged_abort(session_id: str):
    """
    Abort staged session.
    """
    abort_tool(session_id)
    typer.echo("Aborted")


@app.command()
def reader_extract(repo: str, path: str, query: str, regex: bool = False, before: int = 3, after: int = 3):
    """
    Extract from file.
    """
    repo_ref = RepoRef(root=repo)
    intent = ReadIntent(path=path, query=query, regex=regex, before=before, after=after)
    result = extract_tool(repo_ref, intent)
    typer.echo(f"Found {len(result.spans or [])} spans")


@app.command()
def reader_answer(repo: str, path: str, question: str):
    """
    Answer about file.
    """
    repo_ref = RepoRef(root=repo)
    result = answer_about_file_tool(repo_ref, path, question)
    typer.echo(result['answer'])


if __name__ == "__main__":
    app()