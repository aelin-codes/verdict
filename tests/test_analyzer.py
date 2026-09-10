"""Integration tests for the main analyzer."""
import subprocess
from pathlib import Path

import pytest

from verdict.core import analyze
from verdict.core.models import VerdictLevel


@pytest.fixture()
def git_repo(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True, capture_output=True)
    (tmp_path / "auth.py").write_text("def login():\n    pass\n")
    (tmp_path / "tokens.py").write_text("def verify():\n    pass\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


def test_pass_no_change_no_claim(git_repo):
    """No diff, vague claim → PASS."""
    result = analyze(str(git_repo), claim="did some work")
    assert result.level == VerdictLevel.PASS


def test_lied_untouched_file(git_repo):
    """
    Agent claims it changed tokens.py but only auth.py is modified → LIED.
    """
    (git_repo / "auth.py").write_text("def login():\n    return True\n")
    result = analyze(str(git_repo), claim="refactored tokens.py")
    assert result.level == VerdictLevel.LIED
    assert any("tokens.py" in str(c) for c in result.citations)


def test_pass_matching_change(git_repo):
    """Agent claims it changed auth.py and it's in the diff → PASS."""
    (git_repo / "auth.py").write_text("def login():\n    return True\n")
    result = analyze(str(git_repo), claim="updated auth.py login function")
    # May or may not be PASS depending on symbol analysis, but should not be LIED
    assert result.level in (VerdictLevel.PASS, VerdictLevel.SUSPICIOUS)


def test_suspicious_stub(git_repo):
    """Modified file contains a stub → at least SUSPICIOUS."""
    (git_repo / "auth.py").write_text("def authenticate_user():\n    pass\n")
    result = analyze(str(git_repo), claim="implemented authenticate_user in auth.py")
    assert result.level in (VerdictLevel.SUSPICIOUS, VerdictLevel.LIED)


def test_result_to_dict_has_required_keys(git_repo):
    result = analyze(str(git_repo), claim="did some work")
    d = result.to_dict()
    for key in ("verdict", "claim", "explanation", "citations", "static_flags", "trace_flags", "diff_summary"):
        assert key in d, f"Missing key: {key}"


def test_error_on_invalid_git_repo(tmp_path):
    result = analyze(str(tmp_path), claim="did some work")
    assert result.level == VerdictLevel.ERROR
    assert "Not a git repository" in result.explanation


def test_lcov_coverage_tracer(git_repo):
    from verdict.core.tracer import parse_lcov, check_coverage_gaps
    lcov_file = git_repo / "lcov.info"
    lcov_file.write_text(
        "SF:auth.py\n"
        "DA:1,5\n"
        "DA:2,0\n"
        "end_of_record\n"
    )
    executed = parse_lcov(lcov_file, git_repo)
    assert "auth.py" in executed
    assert 1 in executed["auth.py"]
    assert 2 not in executed["auth.py"]

    flags = check_coverage_gaps(executed, ["auth.py"], "claim")
    assert any("executed 1 line(s)" in f for f in flags)
