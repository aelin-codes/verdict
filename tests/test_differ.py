"""Tests for the git differ module."""
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from verdict.core.differ import (
    extract_mentioned_paths,
    get_diff,
    _parse_unified_diff,
)


@pytest.fixture()
def git_repo(tmp_path):
    """Create a minimal git repo with one committed file."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)

    (tmp_path / "auth.py").write_text("def login(): pass\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


def test_get_diff_clean_repo(git_repo):
    """A repo with no uncommitted changes should return an empty diff."""
    diffs = get_diff(str(git_repo))
    assert diffs == []


def test_get_diff_with_change(git_repo):
    (git_repo / "auth.py").write_text("def login(): return True\n\ndef logout(): pass\n")
    diffs = get_diff(str(git_repo))
    assert any(d.path == "auth.py" for d in diffs)


def test_get_diff_invalid_repo(tmp_path):
    with pytest.raises(ValueError, match="Not a git repository"):
        get_diff(str(tmp_path))


def test_extract_mentioned_paths_finds_existing(git_repo):
    paths = extract_mentioned_paths("I updated auth.py to fix the login function", str(git_repo))
    assert "auth.py" in paths


def test_extract_mentioned_paths_ignores_missing(git_repo):
    paths = extract_mentioned_paths("I updated tokens.py", str(git_repo))
    assert paths == []


def test_parse_unified_diff_basic():
    raw = """\
diff --git a/foo.py b/foo.py
index 0000000..1111111 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,3 @@
 def hello():
-    pass
+    return 42
+    # new line
"""
    diffs = _parse_unified_diff(raw)
    assert len(diffs) == 1
    assert diffs[0].path == "foo.py"
    assert diffs[0].added == 2
    assert diffs[0].removed == 1


def test_extract_mentioned_paths_tsx_and_posix(git_repo):
    sub = git_repo / "src" / "components"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "Button.tsx").write_text("export const Button = () => null;\n")
    paths = extract_mentioned_paths("Updated Button.tsx component", str(git_repo))
    assert len(paths) == 1
    assert paths[0] == "src/components/Button.tsx"
    assert "\\" not in paths[0]


def test_get_diff_includes_untracked_files(git_repo):
    new_file = git_repo / "new_service.py"
    new_file.write_text("print('hello world')\n")
    diffs = get_diff(str(git_repo))
    assert any(d.path == "new_service.py" and d.added == 1 for d in diffs)


def test_extract_mentioned_paths_excludes_node_modules(git_repo):
    node_mod = git_repo / "node_modules" / "busboy"
    node_mod.mkdir(parents=True, exist_ok=True)
    (node_mod / "route.ts").write_text("// dummy\n")
    real_dir = git_repo / "src" / "api"
    real_dir.mkdir(parents=True, exist_ok=True)
    (real_dir / "route.ts").write_text("// real\n")

    paths = extract_mentioned_paths("Updated route.ts in api", str(git_repo))
    assert all("node_modules" not in p for p in paths)
    assert "src/api/route.ts" in paths
