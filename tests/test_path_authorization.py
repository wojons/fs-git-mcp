import os
import unittest
from pathlib import Path
from mcp_server.git_backend.safety import PathAuthorizer, create_path_authorizer_from_config, glob_to_regex

class TestPathAuthorization(unittest.TestCase):
    def setUp(self):
        self.repo_root = "/tmp/test-repo"
        os.makedirs(self.repo_root, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.repo_root, ignore_errors=True)

    def test_glob_to_regex_basic(self):
        """Test basic glob to regex conversion."""
        self.assertEqual(glob_to_regex("*.py"), "^[^/]*\\.py$")
        self.assertEqual(glob_to_regex("src/*.py"), "^src/[^/]*\\.py$")
        self.assertEqual(glob_to_regex("**/*.md"), "^.*\\.md$")
        self.assertEqual(glob_to_regex("docs/**/*.txt"), "^docs/.*\\.txt$")
        self.assertEqual(glob_to_regex("a?b"), "^a.b$")
        self.assertEqual(glob_to_regex("[a-z].txt"), "^[a-z]\\.txt$")

    def test_glob_to_regex_edge_cases(self):
        """Test edge cases for glob conversion."""
        self.assertEqual(glob_to_regex(""), "^$")
        self.assertEqual(glob_to_regex("*"), "^[^/]*$")
        self.assertEqual(glob_to_regex("**"), "^.*$")
        self.assertEqual(glob_to_regex("file.txt"), "^file\\.txt$")
        self.assertEqual(glob_to_regex("/root/file"), "^/root/file$")

    def test_path_authorizer_allowed_glob_patterns(self):
        """Test allowed glob patterns."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**", "docs/**/*.md"],
            repo_root=self.repo_root
        )

        # Allowed paths
        self.assertTrue(authorizer.is_path_allowed("src/main.py"))
        self.assertTrue(authorizer.is_path_allowed("src/utils/helper.py"))
        self.assertTrue(authorizer.is_path_allowed("docs/index.md"))
        self.assertTrue(authorizer.is_path_allowed("docs/subdir/guide.md"))

        # Denied paths (no allowed patterns match)
        self.assertFalse(authorizer.is_path_allowed("tests/test.py"))
        self.assertFalse(authorizer.is_path_allowed("config.json"))
        self.assertFalse(authorizer.is_path_allowed("../outside.py"))

    def test_path_authorizer_denied_patterns(self):
        """Test denied patterns with ! prefix."""
        authorizer = PathAuthorizer(
            allowed_patterns=None,  # All allowed by default
            denied_patterns=["**/node_modules/**", "**/.git/**"],
            repo_root=self.repo_root
        )

        # Allowed paths
        self.assertTrue(authorizer.is_path_allowed("src/main.py"))
        self.assertTrue(authorizer.is_path_allowed("docs/guide.md"))

        # Denied paths
        self.assertFalse(authorizer.is_path_allowed("node_modules/package.json"))
        self.assertFalse(authorizer.is_path_allowed("src/node_modules/utils.py"))
        self.assertFalse(authorizer.is_path_allowed(".git/config"))
        self.assertFalse(authorizer.is_path_allowed("docs/.git/hooks/pre-commit"))

    def test_path_authorizer_combined_allow_and_deny(self):
        """Test combined allow and deny patterns."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**", "docs/**"],
            denied_patterns=["**/secrets/**", "**/temp/**"],
            repo_root=self.repo_root
        )

        # Allowed
        self.assertTrue(authorizer.is_path_allowed("src/public.py"))
        self.assertTrue(authorizer.is_path_allowed("docs/guide.md"))

        # Denied by deny pattern (even if allowed by allow)
        self.assertFalse(authorizer.is_path_allowed("src/secrets/key.py"))
        self.assertFalse(authorizer.is_path_allowed("docs/temp/cache.json"))

        # Outside allowed
        self.assertFalse(authorizer.is_path_allowed("tests/test.py"))

    def test_create_from_config_allow_only(self):
        """Test creating authorizer from config string with allow only."""
        authorizer = create_path_authorizer_from_config(
            repo_root=self.repo_root,
            allow_paths="src/**,docs/**"
        )

        self.assertEqual(len(authorizer.allowed_patterns), 2)
        self.assertEqual(len(authorizer.denied_patterns), 0)
        self.assertTrue(authorizer.is_path_allowed("src/app.py"))
        self.assertFalse(authorizer.is_path_allowed("config.yaml"))

    def test_create_from_config_both(self):
        """Test creating with both allow and deny."""
        authorizer = create_path_authorizer_from_config(
            repo_root=self.repo_root,
            allow_paths="src/**",
            deny_paths="!**/private/**,!**/.env"
        )

        self.assertEqual(len(authorizer.allowed_patterns), 1)
        self.assertEqual(len(authorizer.denied_patterns), 2)
        self.assertTrue(authorizer.is_path_allowed("src/public.py"))
        self.assertFalse(authorizer.is_path_allowed("src/private/key.py"))
        self.assertFalse(authorizer.is_path_allowed(".env"))

    def test_create_from_config_whitespace_handling(self):
        """Test handling of whitespace in config strings."""
        authorizer = create_path_authorizer_from_config(
            repo_root=self.repo_root,
            allow_paths="  src/** , docs/**  ",
            deny_paths=" !**/node_modules/** , !**/.git/** "
        )

        self.assertEqual(authorizer.allowed_patterns, ["src/**", "docs/**"])
        self.assertEqual(authorizer.denied_patterns, ["**/node_modules/**", "**/.git/**"])

    def test_allowed_path_relative_absolute(self):
        """Test relative and absolute path handling."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**"],
            repo_root=self.repo_root
        )

        # Relative paths
        self.assertTrue(authorizer.is_path_allowed("src/main.py"))
        self.assertFalse(authorizer.is_path_allowed("tests/test.py"))

        # Absolute paths
        abs_src = os.path.join(self.repo_root, "src", "main.py")
        self.assertTrue(authorizer.is_path_allowed(abs_src))

        abs_tests = os.path.join(self.repo_root, "tests", "test.py")
        self.assertFalse(authorizer.is_path_allowed(abs_tests))

    def test_path_traversal_protection(self):
        """Test path traversal protection."""
        authorizer = PathAuthorizer(
            allowed_patterns=["src/**"],
            repo_root=self.repo_root
        )

        self.assertFalse(authorizer.is_path_allowed("../outside.py"))
        self.assertFalse(authorizer.is_path_allowed("/absolute/outside.py"))
        self.assertFalse(authorizer.is_path_allowed("src/../../etc/passwd"))

    def test_no_patterns_all_allowed(self):
        """Test default behavior with no patterns."""
        authorizer = PathAuthorizer(repo_root=self.repo_root)
        self.assertTrue(authorizer.is_path_allowed("any/path.txt"))

    def test_only_denied_patterns(self):
        """Test only deny patterns, allow all others."""
        authorizer = PathAuthorizer(
            denied_patterns=["secrets/**"],
            repo_root=self.repo_root
        )
        self.assertTrue(authorizer.is_path_allowed("src/main.py"))
        self.assertFalse(authorizer.is_path_allowed("secrets/key.txt"))

    def test_environment_variables(self):
        """Test environment variable fallback."""
        os.environ["FS_GIT_ALLOWED_PATHS"] = "env/src/**"
        os.environ["FS_GIT_DENIED_PATHS"] = "!env/secrets/**"

        authorizer = create_path_authorizer_from_config(repo_root=self.repo_root)
        self.assertEqual(authorizer.allowed_patterns, ["env/src/**"])
        self.assertEqual(authorizer.denied_patterns, ["env/secrets/**"])

        # CLI precedence
        authorizer_cli = create_path_authorizer_from_config(
            repo_root=self.repo_root,
            allow_paths="cli/docs/**"
        )
        self.assertEqual(authorizer_cli.allowed_patterns, ["cli/docs/**"])
        self.assertEqual(authorizer_cli.denied_patterns, [])  # Env denied not used

if __name__ == "__main__":
    unittest.main()
