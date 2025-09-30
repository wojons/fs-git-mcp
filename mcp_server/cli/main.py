import sys
import typer
from pathlib import Path
from typing import Optional
from ..git_backend.repo import RepoRef
from ..git_backend.templates import load_default_template, CommitTemplate
from ..tools.git_fs import write_and_commit_tool, read_with_history_tool, start_staged_tool, staged_write_tool, staged_preview_tool, finalize_tool, abort_tool, lint_commit_message, WriteRequest, FinalizeOptions
from ..tools.reader import extract_tool, answer_about_file_tool, ReadIntent

app = typer.Typer()

# Create subcommand groups
staged_app = typer.Typer(help="Staged session operations")
reader_app = typer.Typer(help="Reader subagent operations")
app.add_typer(staged_app, name="staged")
app.add_typer(reader_app, name="reader")


@app.command()
def init(repo_root: str = typer.Argument(..., help="Repository root path")):
    """
    Initialize a git repository for fs-git usage.
    """
    import subprocess
    import os
    
    # Create directory if it doesn't exist
    os.makedirs(repo_root, exist_ok=True)
    
    # Initialize git repo
    subprocess.run(["git", "init", repo_root], check=True)
    
    # Set safe.directory
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", repo_root], check=True)
    
    # Set default user if not configured
    try:
        subprocess.run(["git", "-C", repo_root, "config", "user.name"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        subprocess.run(["git", "-C", repo_root, "config", "user.name", "FS-Git User"], check=True)
    
    try:
        subprocess.run(["git", "-C", repo_root, "config", "user.email"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        subprocess.run(["git", "-C", repo_root, "config", "user.email", "fs-git@example.com"], check=True)
    
    typer.echo(f"Initialized git repository at {repo_root}")


@app.command()
def write(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
         path: str = typer.Option(..., "--path", help="File path"), 
         file: Optional[str] = typer.Option(None, "--file", help="File to read content from"), 
         subject: str = typer.Option(None, "--subject", help="Commit subject template"), 
         reason: Optional[str] = typer.Option(None, "--reason", help="Reason for change"), 
         ticket: Optional[str] = typer.Option(None, "--ticket", help="Ticket reference"), 
         op: str = typer.Option("edit", "--op", help="Operation type"),
         summary: str = typer.Option("CLI write", "--summary", help="Summary of changes")):
    """
    Write and commit a file.
    """
    repo_ref = RepoRef(root=repo)
    if subject:
        # Use custom subject template
        template = CommitTemplate(subject=subject)
    else:
        template = load_default_template()
    if file and file != '-':
        with open(file, 'r') as f:
            content = f.read()
    elif not sys.stdin.isatty() or file == '-':
        # Read from stdin if it's not a TTY (i.e., piped input) or explicitly requested
        content = sys.stdin.read()
    else:
        content = typer.prompt("Content")
    variables = {'op': str(op), 'path': str(path), 'summary': summary, 'reason': str(reason or ''), 'ticket': str(ticket or ''), 'files': '', 'refs': ''}
    result = write_and_commit_tool(WriteRequest(repo=repo_ref, path=path, content=content, template=template, op=op, summary=summary, reason=reason, ticket=ticket))
    typer.echo(f"Committed {result.commit_sha} on {result.branch}")


# Staged subcommands
@staged_app.command("start")
def staged_start(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
                ticket: Optional[str] = typer.Option(None, "--ticket", help="Ticket reference")):
    """
    Start a staged session.
    """
    repo_ref = RepoRef(root=repo)
    session = start_staged_tool(repo_ref, ticket)
    typer.echo(f"Started session {session.id}")


@staged_app.command("write")
def staged_write(session_id: str = typer.Option(..., "--session", help="Session ID"), 
                 repo: str = typer.Option(..., "--repo", help="Repository root path"), 
                 path: str = typer.Option(..., "--path", help="File path"), 
                 file: Optional[str] = typer.Option(None, "--file", help="File to read content from"), 
                 summary: str = typer.Option("staged write", "--summary", help="Summary of changes")):
    """
    Write in staged session.
    """
    repo_ref = RepoRef(root=repo)
    template = load_default_template()
    if file and file != '-':
        with open(file, 'r') as f:
            content = f.read()
    elif not sys.stdin.isatty() or file == '-':
        # Read from stdin if it's not a TTY (i.e., piped input) or explicitly requested
        content = sys.stdin.read()
    else:
        content = typer.prompt("Content")
    variables = {'op': 'staged', 'path': path, 'summary': summary}
    result = staged_write_tool(session_id, WriteRequest(repo=repo_ref, path=path, content=content, template=template, op='staged', summary=summary))
    typer.echo(f"Staged write {result.commit_sha}")


@staged_app.command("preview")
def staged_preview(session_id: str = typer.Option(..., "--session", help="Session ID")):
    """
    Preview staged changes.
    """
    preview = staged_preview_tool(session_id)
    typer.echo(preview.diff)


@staged_app.command("finalize")
def staged_finalize(session_id: str = typer.Option(..., "--session", help="Session ID"), 
                   strategy: str = typer.Option("merge-ff", "--strategy", help="Merge strategy")):
    """
    Finalize staged session.
    """
    options = FinalizeOptions(strategy=strategy)
    result = finalize_tool(session_id, options)
    typer.echo(f"Finalized {result['merged_sha']}")


@staged_app.command("abort")
def staged_abort(session_id: str = typer.Option(..., "--session", help="Session ID")):
    """
    Abort staged session.
    """
    abort_tool(session_id)
    typer.echo("Aborted")


# Reader subcommands
@reader_app.command("extract")
def reader_extract(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
                   path: str = typer.Option(..., "--path", help="File path"), 
                   query: str = typer.Option(..., "--query", help="Search query"), 
                   regex: bool = typer.Option(False, "--regex", help="Use regex"), 
                   before: int = typer.Option(3, "--before", help="Lines before"), 
                   after: int = typer.Option(3, "--after", help="Lines after")):
    """
    Extract from file.
    """
    repo_ref = RepoRef(root=repo)
    intent = ReadIntent(path=path, query=query, regex=regex, before=before, after=after)
    result = extract_tool(repo_ref, intent)
    typer.echo(f"Found {len(result.spans or [])} spans")
    # Print the actual span content for testing
    if result.spans:
        for span in result.spans:
            if isinstance(span, dict) and 'lines' in span:
                for line in span['lines']:
                    typer.echo(line)


@reader_app.command("answer")
def reader_answer(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
                  path: str = typer.Option(..., "--path", help="File path"), 
                  question: str = typer.Option(..., "--question", help="Question about file")):
    """
    Answer about file.
    """
    repo_ref = RepoRef(root=repo)
    result = answer_about_file_tool(repo_ref, path, question)
    typer.echo(result['answer'])


@app.command()
def replace(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
            path: str = typer.Option(..., "--path", help="File path"), 
            search: str = typer.Option(..., "--search", help="Search pattern"), 
            replace: str = typer.Option(..., "--replace", help="Replacement text"), 
            regex: bool = typer.Option(False, "--regex", help="Use regex"), 
            commit: bool = typer.Option(False, "--commit", help="Commit changes"), 
            summary: str = typer.Option("text replacement", "--summary", help="Commit summary")):
    """
    Replace text in file and optionally commit.
    """
    from ..tools.integrate_text_replace import replace_and_commit
    repo_ref = RepoRef(root=repo)
    template = load_default_template()
    
    if commit:
        result = replace_and_commit(repo_ref, path, search, replace, regex, template, summary)
        typer.echo(f"Replaced and committed {result}")
    else:
        # For now, just show what would be replaced
        typer.echo(f"Would replace '{search}' with '{replace}' in {path}")


@app.command()
def patch(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
          path: str = typer.Option(..., "--path", help="File path"), 
          file: Optional[str] = typer.Option(None, "--file", help="Patch file"), 
          summary: str = typer.Option("apply patch", "--summary", help="Commit summary")):
    """
    Apply patch to file and commit.
    """
    from ..tools.integrate_code_diff import apply_patch_and_commit
    repo_ref = RepoRef(root=repo)
    template = load_default_template()
    
    if file and file != '-':
        with open(file, 'r') as f:
            patch_content = f.read()
    elif not sys.stdin.isatty() or file == '-':
        # Read from stdin if it's not a TTY (i.e., piped input) or explicitly requested
        patch_content = sys.stdin.read()
    else:
        patch_content = typer.prompt("Patch content")
    
    result = apply_patch_and_commit(repo_ref, path, patch_content, template)
    typer.echo(f"Applied patch and committed {result}")


@app.command()
def lint(repo: str = typer.Option(..., "--repo", help="Repository root path"), 
         subject: str = typer.Option(..., "--subject", help="Commit subject template"),
         op: str = typer.Option("edit", "--op", help="Operation type"),
         path: str = typer.Option(..., "--path", help="File path"),
         summary: str = typer.Option("test", "--summary", help="Summary of changes")):
    """
    Lint a commit message template.
    """
    from ..git_backend.templates import CommitTemplate
    repo_ref = RepoRef(root=repo)
    template = CommitTemplate(subject=subject)
    variables = {'op': op, 'path': path, 'summary': summary}
    
    result = lint_commit_message(template, variables)
    if result['ok']:
        typer.echo("✓ Commit message template is valid")
    else:
        typer.echo("✗ Commit message template has errors:")
        for error in result['errors']:
            typer.echo(f"  - {error}")


if __name__ == "__main__":
    app()