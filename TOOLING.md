# Tooling

## MCP Namespaces

### git_fs

- `write_and_commit(WriteRequest) -> WriteResult`
- `read_with_history(repo, path, history_limit?) -> ReadResult`
- `start_staged(repo, ticket?, template?): StagedSession`
- `staged_write(session_id, WriteRequest) -> WriteResult`
- `staged_preview(session_id) -> Preview`
- `finalize(session_id, FinalizeOptions) -> {merged_sha, base_branch}`
- `abort(session_id) -> {status}`

### fs_reader

- `extract(ReadIntent) -> ReadResult`
- `answer_about_file(repo, path, question, ...) -> {answer, citations}`

### fs_text_replace

- `replace_and_commit(repo, path, search, replace, regex?, template) -> WriteResult`
- `batch_replace_and_commit(...) -> {results}`

### fs_code_diff

- `preview_diff(repo, path, modified_content, ...) -> {diff}`
- `apply_patch_and_commit(repo, path, patch, template, staged?) -> WriteResult`

### fs_io

- `read(repo, path) -> string`
- `stat(repo, path) -> {...}`
- `ls(repo, path, recursive?) -> string[]`
- `mkdir(repo, path, recursive?) -> {ok}`

## Schema

See code for Pydantic models.