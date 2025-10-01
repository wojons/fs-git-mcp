import sys
import typer
from pathlib import Path
from typing import Optional
from mcp_server.git_backend.repo import RepoRef
from mcp_server.git_backend.templates import load_default_template, CommitTemplate
from mcp_server.tools.git_fs import (
    write_and_commit_tool,
    read_with_history_tool,
    start_staged_tool,
    staged_write_tool,
    staged_preview_tool,
    finalize_tool,
    abort_tool,
    lint_commit_message,
    WriteRequest,
    FinalizeOptions,
)
from mcp_server.tools.reader import extract_tool, answer_about_file_tool, ReadIntent

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
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", repo_root], check=True
    )

    # Set default user if not configured
    try:
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.name"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.name", "FS-Git User"], check=True
        )

    try:
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.email"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.email", "fs-git@example.com"],
            check=True,
        )

    typer.echo(f"Initialized git repository at {repo_root}")


@app.command()
def write(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    path: str = typer.Option(..., "--path", help="File path"),
    file: Optional[str] = typer.Option(
        None, "--file", help="File to read content from"
    ),
    subject: str = typer.Option(None, "--subject", help="Commit subject template"),
    reason: Optional[str] = typer.Option(None, "--reason", help="Reason for change"),
    ticket: Optional[str] = typer.Option(None, "--ticket", help="Ticket reference"),
    op: str = typer.Option("edit", "--op", help="Operation type"),
    summary: str = typer.Option("CLI write", "--summary", help="Summary of changes"),
    allow_paths: Optional[str] = typer.Option(
        None,
        "--allow-paths",
        help="Comma-separated allowed path patterns (e.g., src/**,docs/**/*.md)",
    ),
    deny_paths: Optional[str] = typer.Option(
        None,
        "--deny-paths",
        help="Comma-separated denied path patterns with ! prefix (e.g., !**/node_modules/**,!**/.git/**)",
    ),
):
    """
    Write and commit a file.
    """
    repo_ref = RepoRef(root=repo)
    if subject:
        # Use custom subject template
        template = CommitTemplate(subject=subject)
    else:
        template = load_default_template()
    if file and file != "-":
        with open(file, "r") as f:
            content = f.read()
    elif not sys.stdin.isatty() or file == "-":
        # Read from stdin if it's not a TTY (i.e., piped input) or explicitly requested
        content = sys.stdin.read()
    else:
        content = typer.prompt("Content")
    variables = {
        "op": str(op),
        "path": str(path),
        "summary": summary,
        "reason": str(reason or ""),
        "ticket": str(ticket or ""),
        "files": "",
        "refs": "",
    }

    # Always check for path authorization (CLI params take precedence over env vars)
    from mcp_server.git_backend.safety import create_path_authorizer_from_config

    path_authorizer = create_path_authorizer_from_config(
        repo_root=repo, allow_paths=allow_paths, deny_paths=deny_paths
    )

    # Only show authorization info if patterns are configured (CLI or env vars)
    has_patterns = bool(
        allow_paths
        or deny_paths
        or path_authorizer.allowed_patterns
        or path_authorizer.denied_patterns
    )

    if has_patterns:
        typer.echo(
            f"Path authorization enabled: {path_authorizer.get_allowed_paths_summary()}"
        )
        typer.echo(f"Denied paths: {path_authorizer.get_denied_paths_summary()}")

    result = write_and_commit_tool(
        WriteRequest(
            repo=repo_ref,
            path=path,
            content=content,
            template=template,
            op=op,
            summary=summary,
            reason=reason,
            ticket=ticket,
            allow_paths=allow_paths,
            deny_paths=deny_paths,
            path_authorizer=path_authorizer,
        )
    )
    typer.echo(f"Committed {result.commit_sha} on {result.branch}")


# Staged subcommands
@staged_app.command("start")
def staged_start(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    ticket: Optional[str] = typer.Option(None, "--ticket", help="Ticket reference"),
):
    """
    Start a staged session.
    """
    repo_ref = RepoRef(root=repo)
    session = start_staged_tool(repo_ref, ticket)
    typer.echo(f"Started session {session.id}")


@staged_app.command("write")
def staged_write(
    session_id: str = typer.Option(..., "--session", help="Session ID"),
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    path: str = typer.Option(..., "--path", help="File path"),
    file: Optional[str] = typer.Option(
        None, "--file", help="File to read content from"
    ),
    summary: str = typer.Option("staged write", "--summary", help="Summary of changes"),
    allow_paths: Optional[str] = typer.Option(
        None, "--allow-paths", help="Comma-separated allowed path patterns"
    ),
    deny_paths: Optional[str] = typer.Option(
        None, "--deny-paths", help="Comma-separated denied path patterns"
    ),
):
    """
    Write in staged session.
    """
    repo_ref = RepoRef(root=repo)
    template = load_default_template()
    if file and file != "-":
        with open(file, "r") as f:
            content = f.read()
    elif not sys.stdin.isatty() or file == "-":
        # Read from stdin if it's not a TTY (i.e., piped input) or explicitly requested
        content = sys.stdin.read()
    else:
        content = typer.prompt("Content")
    variables = {"op": "staged", "path": path, "summary": summary}

    # Create path authorizer if path patterns are provided
    path_authorizer = None
    if allow_paths or deny_paths:
        from mcp_server.git_backend.safety import create_path_authorizer_from_config

        path_authorizer = create_path_authorizer_from_config(
            repo_root=repo, allow_paths=allow_paths, deny_paths=deny_paths
        )
        typer.echo(
            f"Path authorization enabled: {path_authorizer.get_allowed_paths_summary()}"
        )
        typer.echo(f"Denied paths: {path_authorizer.get_denied_paths_summary()}")

    result = staged_write_tool(
        session_id,
        WriteRequest(
            repo=repo_ref,
            path=path,
            content=content,
            template=template,
            op="staged",
            summary=summary,
            allow_paths=allow_paths,
            deny_paths=deny_paths,
            path_authorizer=path_authorizer,
        ),
    )
    typer.echo(f"Staged write {result.commit_sha}")


@staged_app.command("preview")
def staged_preview(session_id: str = typer.Option(..., "--session", help="Session ID")):
    """
    Preview staged changes.
    """
    preview = staged_preview_tool(session_id)
    typer.echo(preview.diff)


@staged_app.command("finalize")
def staged_finalize(
    session_id: str = typer.Option(..., "--session", help="Session ID"),
    strategy: str = typer.Option("merge-ff", "--strategy", help="Merge strategy"),
):
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
def reader_extract(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    path: str = typer.Option(..., "--path", help="File path"),
    query: str = typer.Option(..., "--query", help="Search query"),
    regex: bool = typer.Option(False, "--regex", help="Use regex"),
    before: int = typer.Option(3, "--before", help="Lines before"),
    after: int = typer.Option(3, "--after", help="Lines after"),
):
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
            if isinstance(span, dict) and "lines" in span:
                for line in span["lines"]:
                    typer.echo(line)


@reader_app.command("answer")
def reader_answer(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    path: str = typer.Option(..., "--path", help="File path"),
    question: str = typer.Option(..., "--question", help="Question about file"),
):
    """
    Answer about file.
    """
    repo_ref = RepoRef(root=repo)
    result = answer_about_file_tool(repo_ref, path, question)
    typer.echo(result["answer"])


@app.command()
def replace(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    path: str = typer.Option(..., "--path", help="File path"),
    search: str = typer.Option(..., "--search", help="Search pattern"),
    replace: str = typer.Option(..., "--replace", help="Replacement text"),
    regex: bool = typer.Option(False, "--regex", help="Use regex"),
    commit: bool = typer.Option(False, "--commit", help="Commit changes"),
    summary: str = typer.Option("text replacement", "--summary", help="Commit summary"),
    allow_paths: Optional[str] = typer.Option(
        None, "--allow-paths", help="Comma-separated allowed path patterns"
    ),
    deny_paths: Optional[str] = typer.Option(
        None, "--deny-paths", help="Comma-separated denied path patterns"
    ),
):
    """
    Replace text in file and optionally commit.
    """
    from mcp_server.tools.integrate_text_replace import replace_and_commit
    from mcp_server.git_backend.safety import (
        create_path_authorizer_from_config,
        enforce_path_authorization,
    )

    repo_ref = RepoRef(root=repo)
    template = load_default_template()

    # Create path authorizer if path patterns are provided
    if allow_paths or deny_paths:
        path_authorizer = create_path_authorizer_from_config(
            repo_root=repo, allow_paths=allow_paths, deny_paths=deny_paths
        )
        typer.echo(
            f"Path authorization enabled: {path_authorizer.get_allowed_paths_summary()}"
        )
        typer.echo(f"Denied paths: {path_authorizer.get_denied_paths_summary()}")

        # Check if path is authorized
        try:
            enforce_path_authorization(path, path_authorizer)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

    if commit:
        result = replace_and_commit(
            repo_ref, path, search, replace, regex, template, summary
        )
        typer.echo(f"Replaced and committed {result}")
    else:
        # For now, just show what would be replaced
        typer.echo(f"Would replace '{search}' with '{replace}' in {path}")


@app.command()
def patch(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    path: str = typer.Option(..., "--path", help="File path"),
    file: Optional[str] = typer.Option(None, "--file", help="Patch file"),
    summary: str = typer.Option("apply patch", "--summary", help="Commit summary"),
    allow_paths: Optional[str] = typer.Option(
        None, "--allow-paths", help="Comma-separated allowed path patterns"
    ),
    deny_paths: Optional[str] = typer.Option(
        None, "--deny-paths", help="Comma-separated denied path patterns"
    ),
):
    """
    Apply patch to file and commit.
    """
    from mcp_server.tools.integrate_code_diff import apply_patch_and_commit
    from mcp_server.git_backend.safety import (
        create_path_authorizer_from_config,
        enforce_path_authorization,
    )

    repo_ref = RepoRef(root=repo)
    template = load_default_template()

    # Create path authorizer if path patterns are provided
    if allow_paths or deny_paths:
        path_authorizer = create_path_authorizer_from_config(
            repo_root=repo, allow_paths=allow_paths, deny_paths=deny_paths
        )
        typer.echo(
            f"Path authorization enabled: {path_authorizer.get_allowed_paths_summary()}"
        )
        typer.echo(f"Denied paths: {path_authorizer.get_denied_paths_summary()}")

        # Check if path is authorized
        try:
            enforce_path_authorization(path, path_authorizer)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

    if file and file != "-":
        with open(file, "r") as f:
            patch_content = f.read()
    elif not sys.stdin.isatty() or file == "-":
        # Read from stdin if it's not a TTY (i.e., piped input) or explicitly requested
        patch_content = sys.stdin.read()
    else:
        patch_content = typer.prompt("Patch content")

    result = apply_patch_and_commit(repo_ref, path, patch_content, template)
    typer.echo(f"Applied patch and committed {result}")


@app.command()
def lint(
    repo: str = typer.Option(..., "--repo", help="Repository root path"),
    subject: str = typer.Option(..., "--subject", help="Commit subject template"),
    op: str = typer.Option("edit", "--op", help="Operation type"),
    path: str = typer.Option(..., "--path", help="File path"),
    summary: str = typer.Option("test", "--summary", help="Summary of changes"),
):
    """
    Lint a commit message template.
    """
    from mcp_server.git_backend.templates import CommitTemplate

    repo_ref = RepoRef(root=repo)
    template = CommitTemplate(subject=subject)
    variables = {"op": op, "path": path, "summary": summary}

    result = lint_commit_message(template, variables)
    if result["ok"]:
        typer.echo("✓ Commit message template is valid")
    else:
        typer.echo("✗ Commit message template has errors:")
        for error in result["errors"]:
            typer.echo(f"  - {error}")


@app.command()
def serve(
    transport: str = typer.Option(
        "stdio", "--transport", help="Transport mode: stdio or tcp"
    ),
    port: int = typer.Option(8080, "--port", help="Port for TCP transport"),
    host: str = typer.Option("localhost", "--host", help="Host for TCP transport"),
):
    """
    Start the MCP server for git-enforced filesystem operations.

    Uses stdio transport by default for compatibility with Claude Desktop and MCP Inspector.
    Use TCP transport for development and testing.
    """
    # Fix for Typer option parsing issue - ensure transport is string
    if not isinstance(transport, str):
        transport = "stdio"
    if transport is None:
        transport = "stdio"

    if transport == "stdio":
        typer.echo("Starting fs-git MCP server on stdio...", err=True)
        typer.echo("Use with Claude Desktop or MCP Inspector", err=True)

        # For stdio transport, run directly in this process
        from mcp_server.server_fastmcp_new import main as mcp_main
        mcp_main()

    elif transport == "tcp":
        typer.echo(f"Starting fs-git MCP server on tcp://{host}:{port}", err=True)

        # For TCP mode, run the server on TCP
        from mcp_server.server_fastmcp_new import main as mcp_main
        # Note: FastMCP supports TCP via --transport tcp --host host --port port
        # But for simplicity, call with args
        import subprocess
        subprocess.run([sys.executable, "-m", "mcp_server.server_fastmcp_new", "--transport", "tcp", "--host", host, "--port", str(port)])

    else:
        typer.echo(f"Unknown transport: {transport}", err=True)
        typer.echo("Supported transports: stdio, tcp", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
