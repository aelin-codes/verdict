"""Tests for AST static analysis."""
import textwrap
from pathlib import Path

import pytest

from verdict.core.ast_checker import (
    check_missing_test_coverage,
    detect_stub_implementations,
)


@pytest.fixture()
def py_file(tmp_path):
    """Helper: write a .py file and return its path."""
    def _write(name: str, src: str) -> Path:
        p = tmp_path / name
        p.write_text(textwrap.dedent(src))
        return p
    return _write


def test_detect_stub_pass(tmp_path, py_file):
    py_file("stubs.py", """
        def do_thing():
            pass
    """)
    flags = detect_stub_implementations(str(tmp_path), ["stubs.py"])
    assert any("do_thing" in f.reason for f in flags)


def test_detect_stub_ellipsis(tmp_path, py_file):
    py_file("stubs.py", """
        def do_thing():
            ...
    """)
    flags = detect_stub_implementations(str(tmp_path), ["stubs.py"])
    assert any("do_thing" in f.reason for f in flags)


def test_detect_stub_real_impl(tmp_path, py_file):
    py_file("real.py", """
        def do_thing():
            return 42
    """)
    flags = detect_stub_implementations(str(tmp_path), ["real.py"])
    assert flags == []


def test_detect_stub_docstring_only(tmp_path, py_file):
    py_file("stubs.py", """
        def do_thing():
            \"\"\"Does a thing.\"\"\"
            pass
    """)
    flags = detect_stub_implementations(str(tmp_path), ["stubs.py"])
    assert any("do_thing" in f.reason for f in flags)


def test_no_test_coverage_flag_when_no_test_mention(tmp_path):
    flags = check_missing_test_coverage("refactored auth", str(tmp_path), ["auth.py"])
    assert flags == []


def test_no_test_coverage_flag_no_test_files(tmp_path):
    flags = check_missing_test_coverage("added tests for auth", str(tmp_path), ["auth.py"])
    assert any("no test files" in f.reason for f in flags)


def test_test_file_no_functions(tmp_path, py_file):
    py_file("test_auth.py", "x = 1\n")
    flags = check_missing_test_coverage(
        "added tests", str(tmp_path), ["test_auth.py"]
    )
    assert any("no test_ functions" in f.reason for f in flags)


def test_test_file_with_functions(tmp_path, py_file):
    py_file("test_auth.py", "def test_login(): assert True\n")
    flags = check_missing_test_coverage(
        "added tests", str(tmp_path), ["test_auth.py"]
    )
    assert flags == []


def test_claim_stop_words_and_filename_not_flagged(tmp_path, py_file):
    from verdict.core.ast_checker import check_claim_against_ast
    py_file("backend_helper.py", """
        def helper_func():
            return 42
    """)
    flags = check_claim_against_ast(
        "Added helper_func in scripts/backend_helper.py",
        str(tmp_path),
        ["backend_helper.py"],
    )
    assert flags == []


def test_detect_stub_polyglot_ts(tmp_path):
    ts_file = tmp_path / "authService.ts"
    ts_file.write_text("export function loginUser() {\n  // empty\n}\n")
    flags = detect_stub_implementations(str(tmp_path), ["authService.ts"])
    assert any("loginUser" in f.reason for f in flags)


def test_check_missing_test_coverage_polyglot_ts(tmp_path):
    test_file = tmp_path / "auth.test.ts"
    test_file.write_text("describe('auth', () => { it('works', () => {}); });\n")
    flags = check_missing_test_coverage("added unit tests", str(tmp_path), ["auth.test.ts"])
    assert flags == []
