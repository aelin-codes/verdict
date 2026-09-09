"""Tests for core data models."""
import pytest
from verdict.core.models import Citation, FileDiff, VerdictLevel, VerdictResult


def test_verdict_level_values():
    assert VerdictLevel.PASS.value == "PASS"
    assert VerdictLevel.SUSPICIOUS.value == "SUSPICIOUS"
    assert VerdictLevel.LIED.value == "LIED"


def test_citation_str_single_line():
    c = Citation(file="src/auth.py", line_start=42, line_end=None, reason="untouched")
    assert str(c) == "src/auth.py:42  —  untouched"


def test_citation_str_range():
    c = Citation(file="src/auth.py", line_start=10, line_end=20, reason="stub")
    assert "10-20" in str(c)


def test_verdict_result_to_dict():
    result = VerdictResult(
        level=VerdictLevel.PASS,
        claim="refactored auth",
        explanation="All good.",
    )
    d = result.to_dict()
    assert d["verdict"] == "PASS"
    assert d["claim"] == "refactored auth"
    assert d["citations"] == []
    assert d["static_flags"] == []


def test_verdict_result_with_citations():
    c = Citation(file="foo.py", line_start=1, line_end=None, reason="claimed-but-untouched")
    result = VerdictResult(
        level=VerdictLevel.LIED,
        claim="changed foo.py",
        citations=[c],
        explanation="Lied.",
    )
    d = result.to_dict()
    assert len(d["citations"]) == 1
    assert d["citations"][0]["file"] == "foo.py"
