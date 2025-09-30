import pytest
from mcp_server.git_backend.safety import enforce_repo_root, validate_commit_message


def test_enforce_repo_root_valid():
    assert enforce_repo_root('/tmp/repo', '/tmp/repo/file.txt') == True


def test_enforce_repo_root_invalid():
    assert enforce_repo_root('/tmp/repo', '/tmp/other/file.txt') == False


def test_validate_commit_message_valid():
    ok, errors = validate_commit_message('[{op}] {path} – {summary}')
    assert ok == True
    assert errors == []


def test_validate_commit_message_invalid_length():
    ok, errors = validate_commit_message('a' * 73)
    assert ok == False
    assert 'exceeds 72 characters' in errors[0]


def test_validate_commit_message_missing_tokens():
    ok, errors = validate_commit_message('missing tokens')
    assert ok == False
    assert 'must include' in errors[0]