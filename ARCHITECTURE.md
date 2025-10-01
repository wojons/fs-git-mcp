# Architecture

## Overview

The FS-Git MCP server provides Git-enforced filesystem operations with direct and staged modes.

## Modules

- **git_backend/**: Core git operations.
  - `repo.py`: RepoRef model and git repo management.
  - `safety.py`: Path enforcement, safe.directory, dirty tree checks.
  - `commits.py`: Write, add, commit with templates and uniqueness.
  - `history.py`: Read with git history.
  - `staging.py`: Staged sessions with branch management.
  - `templates.py`: Commit message templates and rendering.

- **tools/**: MCP tool implementations.
  - `git_fs.py`: Main git_fs namespace tools.
  - `reader.py`: Reader subagent for extraction and answering.
  - `integrate_*.py`: Wrappers for existing tools with git semantics.

- **cli/**: Developer CLI using Typer.

## Flows

### Direct Mode
1. Validate path and repo.
2. Write file.
3. Git add.
4. Render template.
5. Check uniqueness.
6. Git commit.

### Staged Mode
1. Create work branch from base.
2. Stage writes on work branch.
3. Preview diff and commits.
4. Finalize: merge/rebase into base, delete work branch.
5. Abort: delete work branch.

## Path Authorization

The `safety.py` module implements PathAuthorizer class for controlling access.

### Features
- **Glob Patterns**: Support `**` for recursive, `*` for wildcards (e.g., `src/**`, `docs/**/*.md`).
- **Regex Patterns**: Full regex support for complex matching.
- **Deny Precedence**: Deny patterns (`!prefix`) override allow.
- **CLI/Env Config**: CLI params override env vars `FS_GIT_ALLOWED_PATHS` and `FS_GIT_DENIED_PATHS`.

### Implementation
- `_matches_glob`: Custom recursive matcher for ** and multi-part globs.
- `_matches_regex`: Standard re.search on relative paths.
- `is_path_allowed`: Check deny first, then allow; default allow if no patterns.

### Integration
- Loaded in CLI and tools via `create_path_authorizer_from_config`.
- Enforced in `enforce_path_authorization` before operations.

## Error Handling

- Path traversal: Raise ValueError.
- Dirty tree: Raise if not allowed.
- Invalid template: Raise with errors.
- Uniqueness: Raise or auto-suffix.
- Conflicts: Surface with markers.